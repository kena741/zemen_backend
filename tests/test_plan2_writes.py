import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.deps import AuthContext, get_auth_context
from app.core.services.profile_service import filter_customer_patch, filter_provider_patch
from app.core.services.provider_documents import upsert_documents
from app.core.services.service_likes import set_like
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
    def __init__(self, results):
        self.results = list(results)
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


def _client(ctx: AuthContext, db: _Db | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_auth_context] = lambda: ctx

    async def _db():
        yield db or _Db([])

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_create_endpoints_do_not_accept_wallet_fields():
    assert "wallet_amount" not in filter_customer_patch({"wallet_amount": 99, "first_name": "A"})
    assert "wallet_amount" not in filter_provider_patch({"wallet_amount": "99", "activation_paid": True})


def test_like_and_unlike_are_auth_only():
    app = create_app()
    client = TestClient(app)
    sid = uuid4()
    assert client.put(f"/api/v1/catalog/services/{sid}/like").status_code == 401
    assert client.delete(f"/api/v1/catalog/services/{sid}/like").status_code == 401


def test_like_toggles_only_the_caller():
    caller = uuid4()
    other = str(uuid4())
    service = SimpleNamespace(id=uuid4(), liked_user=[other])

    class _LikeDb(_Db):
        async def execute(self, stmt, _params=None):
            return _Rows(scalar=service)

    db = _LikeDb([])
    out = asyncio.run(set_like(db, service.id, caller, liked=True))
    assert str(caller) in out.liked_user
    assert other in out.liked_user
    out = asyncio.run(set_like(db, service.id, caller, liked=False))
    assert str(caller) not in out.liked_user
    assert other in out.liked_user


def test_document_upsert_forces_unverified_and_skips_unknown_types():
    provider_id = uuid4()
    known = uuid4()
    unknown = uuid4()
    db = _Db([_Rows(scalar=known), _Rows(), _Rows(scalar=None)])
    rows = asyncio.run(
        upsert_documents(
            db,
            provider_id=provider_id,
            provider_name="P",
            provider_email="p@x.com",
            items=[
                {"document_id": known, "document_image": "path/a.jpg", "is_verify": True},
                {"document_id": unknown, "document_image": "path/b.jpg"},
            ],
        )
    )
    assert len(rows) == 1
    assert rows[0].is_verify is False
    assert rows[0].provider_id == provider_id


def test_payment_methods_and_documents_require_provider():
    client = _client(_ctx(customer=True))
    assert client.get("/api/v1/providers/me/payment-methods").status_code == 403
    assert client.get("/api/v1/providers/me/documents").status_code == 403
    assert _client(_ctx()).get("/api/v1/customers/me/service-details").status_code == 403
