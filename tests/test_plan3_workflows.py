import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.deps import AuthContext, get_auth_context
from app.core.services import booking_actions, job_service, notification_service, offer_service
from app.persistence.sqlalchemy.deps import get_db


class _Rows:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        if self._scalar is not None:
            return self._scalar
        return self._rows[0] if self._rows else None


class _Db:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.deleted = []
        self.flushed = 0

    async def execute(self, stmt, _params=None):
        return self.results.pop(0) if self.results else _Rows()

    def add(self, row):
        self.added.append(row)

    async def delete(self, row):
        self.deleted.append(row)

    async def flush(self):
        self.flushed += 1

    async def refresh(self, row):
        return row


def _ctx(*, customer=False, provider=False) -> AuthContext:
    uid = uuid4()
    return AuthContext(
        user_id=uid,
        email="a@b.com",
        roles=(["customer"] if customer else []) + (["provider"] if provider else []) or ["authenticated"],
        customer_id=uid if customer else None,
        provider_id=uid if provider else None,
    )


def _client(ctx: AuthContext | None = None, db: _Db | None = None) -> TestClient:
    app = create_app()
    if ctx is not None:
        app.dependency_overrides[get_auth_context] = lambda: ctx

    async def _db():
        yield db or _Db()

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_new_plan3_routes_require_auth():
    client = TestClient(create_app())
    sid = str(uuid4())
    assert client.post(f"/api/v1/bookings/{sid}/cancel", json={}).status_code == 401
    assert client.post("/api/v1/jobs", json={"title": "t"}).status_code == 401
    assert client.post(f"/api/v1/jobs/{sid}/close").status_code == 401
    assert client.post(f"/api/v1/jobs/{sid}/bid", json={"bidPrice": "10"}).status_code == 401
    assert client.post("/api/v1/offers", json={"serviceId": sid, "offeredPrice": 1}).status_code == 401
    assert client.post(f"/api/v1/offers/{sid}/accept").status_code == 401
    assert client.post("/api/v1/notifications/read", json={}).status_code == 401
    assert client.delete("/api/v1/notifications").status_code == 401


def test_job_and_offer_writes_require_role():
    customer = _client(_ctx(customer=True))
    provider = _client(_ctx(provider=True))
    sid = str(uuid4())
    assert customer.post(f"/api/v1/jobs/{sid}/bid", json={"bidPrice": "10"}).status_code == 403
    assert provider.post("/api/v1/jobs", json={"title": "t"}).status_code == 403
    assert provider.post("/api/v1/offers", json={"serviceId": sid, "offeredPrice": 5}).status_code == 403


def test_create_job_is_open_listing_and_ignores_is_paid():
    db = _Db([_Rows()])
    row = asyncio.run(
        job_service.create_job(
            db,
            customer_id=uuid4(),
            data={"id": "job-1", "title": "Fix sink", "price": "100", "is_paid": True},
        )
    )
    assert row.status == "accepted"
    assert row.is_paid is False
    assert row.accepted is False
    assert row.provider_id is None
    assert row.id == "job-1"


def test_close_job_uses_rejected_enum():
    customer_id = uuid4()
    job = SimpleNamespace(id="job-1", customer_id=customer_id, status="accepted", accepted=True)

    async def _get(_db, job_id):
        return job if job_id == "job-1" else None

    with patch.object(job_service, "get_job", _get):
        out = asyncio.run(job_service.close_job(_Db(), job_id="job-1", customer_id=customer_id))
    assert out.status == "rejected"
    assert out.accepted is False


def test_bid_does_not_assign_provider_and_uses_auth_uid():
    user_id = uuid4()
    job = SimpleNamespace(
        id="job-1",
        status="accepted",
        bid_list=[{"providerId": "other", "price": "5"}],
        bid_price=None,
        provider_id=None,
    )

    async def _get(_db, job_id):
        return job

    with patch.object(job_service, "get_job", _get):
        out = asyncio.run(job_service.add_bid(_Db(), job_id="job-1", user_id=user_id, bid_price="12"))
    assert out.provider_id is None
    assert out.bid_price == "12"
    assert any(b.get("providerId") == str(user_id) and b.get("price") == "12" for b in out.bid_list)
    assert any(b.get("providerId") == "other" for b in out.bid_list)


def test_cancel_booking_rejects_and_cancels_pending_offers():
    customer_id = uuid4()
    booking_id = uuid4()
    booking = SimpleNamespace(
        id=booking_id,
        customer_id=customer_id,
        customer_user_id=customer_id,
        status="pending",
        reason=None,
        service_id=uuid4(),
    )
    offer = SimpleNamespace(booking_id=str(booking_id), status="pending")
    db = _Db([_Rows(rows=[offer])])

    with patch(
        "app.core.services.booking_actions.booking_service.get_booking",
        AsyncMock(return_value=booking),
    ):
        out = asyncio.run(
            booking_actions.cancel_booking(
                db, booking_id=booking_id, customer_id=customer_id, user_id=customer_id, reason="changed mind"
            )
        )
    assert out.status == "rejected"
    assert out.reason == "changed mind"
    assert offer.status == "cancelled"


def test_cancel_booking_forbidden_for_other_customer():
    booking = SimpleNamespace(
        id=uuid4(),
        customer_id=uuid4(),
        customer_user_id=uuid4(),
        status="pending",
        reason=None,
        service_id=None,
    )
    with patch(
        "app.core.services.booking_actions.booking_service.get_booking",
        AsyncMock(return_value=booking),
    ):
        try:
            asyncio.run(
                booking_actions.cancel_booking(
                    _Db(), booking_id=booking.id, customer_id=uuid4(), user_id=uuid4(), reason=None
                )
            )
            raise AssertionError("expected forbidden")
        except HTTPException as exc:
            assert exc.status_code == 403


def test_cancel_completed_booking_conflicts():
    customer_id = uuid4()
    booking = SimpleNamespace(
        id=uuid4(),
        customer_id=customer_id,
        customer_user_id=customer_id,
        status="completed",
        reason=None,
        service_id=None,
    )
    with patch(
        "app.core.services.booking_actions.booking_service.get_booking",
        AsyncMock(return_value=booking),
    ):
        try:
            asyncio.run(
                booking_actions.cancel_booking(
                    _Db(), booking_id=booking.id, customer_id=customer_id, user_id=customer_id
                )
            )
            raise AssertionError("expected conflict")
        except HTTPException as exc:
            assert exc.status_code == 409


def test_offer_create_requires_custom_price_flag():
    service = SimpleNamespace(id=uuid4(), provider_id=uuid4(), allows_custom_offer=False)
    db = _Db([_Rows(scalar=service)])
    try:
        asyncio.run(
            offer_service.create_offer(
                db,
                customer_id=uuid4(),
                user_id=uuid4(),
                data={"service_id": service.id, "offered_price": "20"},
            )
        )
        raise AssertionError("expected 400")
    except HTTPException as exc:
        assert exc.status_code == 400


def test_offer_accept_is_provider_only():
    offer = SimpleNamespace(
        id=uuid4(),
        status="pending",
        customer_id=str(uuid4()),
        provider_id=str(uuid4()),
        updated_at=None,
    )

    async def _get(_db, _id):
        return offer

    with patch.object(offer_service, "get_offer", _get):
        try:
            asyncio.run(
                offer_service.set_offer_status(
                    _Db(),
                    offer_id=offer.id,
                    new_status="accepted",
                    customer_id=uuid4(),
                    user_id=uuid4(),
                )
            )
            raise AssertionError("expected forbidden")
        except HTTPException as exc:
            assert exc.status_code == 403


def test_offer_cancel_is_customer_only_and_pending():
    customer_id = uuid4()
    offer = SimpleNamespace(
        id=uuid4(),
        status="pending",
        customer_id=str(customer_id),
        provider_id=str(uuid4()),
        updated_at=None,
    )

    async def _get(_db, _id):
        return offer

    with patch.object(offer_service, "get_offer", _get):
        out = asyncio.run(
            offer_service.set_offer_status(
                _Db(),
                offer_id=offer.id,
                new_status="cancelled",
                customer_id=customer_id,
                user_id=customer_id,
            )
        )
    assert out.status == "cancelled"


def test_attach_booking_requires_accepted_offer():
    customer_id = uuid4()
    offer = SimpleNamespace(
        id=uuid4(),
        status="pending",
        customer_id=str(customer_id),
        booking_id=None,
        updated_at=None,
    )

    async def _get(_db, _id):
        return offer

    with patch.object(offer_service, "get_offer", _get):
        try:
            asyncio.run(
                offer_service.attach_booking(
                    _Db(),
                    offer_id=offer.id,
                    booking_id=str(uuid4()),
                    customer_id=customer_id,
                    user_id=customer_id,
                )
            )
            raise AssertionError("expected conflict")
        except HTTPException as exc:
            assert exc.status_code == 409


def test_notification_mark_and_delete_are_scoped():
    mine = SimpleNamespace(id=uuid4(), customer_id=uuid4(), is_read=False, read_at=None)
    db = _Db([_Rows(rows=[mine]), _Rows(rows=[mine])])
    marked = asyncio.run(
        notification_service.mark_read(
            db, user_id=mine.customer_id, customer_id=mine.customer_id, provider_id=None, handyman_id=None
        )
    )
    assert marked == 1
    assert mine.is_read is True
    deleted = asyncio.run(
        notification_service.delete_owned(
            db, user_id=mine.customer_id, customer_id=mine.customer_id, provider_id=None, handyman_id=None, ids=[mine.id]
        )
    )
    assert deleted == 1
    assert db.deleted == [mine]
