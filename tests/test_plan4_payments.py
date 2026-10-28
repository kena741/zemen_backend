from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.deps import AuthContext
from app.core.services.chapa_client import verify_tx_ref
from app.core.services.commission import provider_net
from app.core.services.payment_writes import refund_booking, refund_note
from app.config import settings


def test_payment_status_reports_disabled():
    client = TestClient(create_app())
    resp = client.get("/api/v1/payments/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["chapaConfigured"] is False or "chapaConfigured" in body


def test_payment_writes_are_503_while_gated():
    assert settings.PAYMENTS_WRITES_ENABLED is False
    app = create_app()
    uid = uuid4()

    async def _ctx():
        return AuthContext(user_id=uid, email="a@b.com", roles=["customer"], customer_id=uid)

    from app.core.security.deps import get_auth_context

    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=uid, email="a@b.com", roles=["customer", "provider"], customer_id=uid, provider_id=uid
    )
    client = TestClient(app)
    bid = str(uuid4())
    assert client.post("/api/v1/payments/chapa/verify", json={"txRef": "tx-123456", "purpose": "wallet"}).status_code == 503
    assert client.post(f"/api/v1/payments/bookings/{bid}/refund").status_code == 503
    assert client.post(f"/api/v1/payments/bookings/{bid}/complete").status_code == 503
    assert client.post("/api/v1/wallet/withdrawals", json={"amount": "10"}).status_code == 503


def test_commission_uses_numeric_booking_amount_not_object():
    gross = Decimal("100")
    assert provider_net(gross, booking_commission=Decimal("15"), rule={"isFix": False, "value": 50}) == Decimal("85")
    assert provider_net(gross, booking_commission=None, rule={"isFix": True, "value": 10}) == Decimal("90")
    assert provider_net(gross, booking_commission=None, rule={"isFix": False, "value": 10}) == Decimal("90")
    assert provider_net(gross, booking_commission=None, rule=None) == Decimal("100")


def test_chapa_rejects_bad_ref_and_missing_env():
    import asyncio

    try:
        asyncio.run(verify_tx_ref("bad"))
        raise AssertionError("expected invalid ref")
    except HTTPException as exc:
        assert exc.status_code == 400
    try:
        asyncio.run(verify_tx_ref("tx-abcdef"))
        raise AssertionError("expected missing env")
    except HTTPException as exc:
        assert exc.status_code == 503


def test_ledger_skips_duplicate_credit():
    import asyncio
    from app.core.services import ledger

    existing = SimpleNamespace(id=uuid4(), amount="10.00")

    async def _found(*_a, **_k):
        return existing

    with patch.object(ledger, "find_existing", _found):
        row, created = asyncio.run(
            ledger.apply_ledger(
                SimpleNamespace(),
                kind="customer",
                owner_id=uuid4(),
                user_id=uuid4(),
                amount=Decimal("10"),
                is_credit=True,
                note="Wallet top-up",
                transaction_id="tx-1",
                payment_type="chapa",
            )
        )
    assert created is False
    assert row is existing


def test_refund_rejects_completed_booking():
    import asyncio

    ctx = AuthContext(
        user_id=uuid4(),
        email="a@b.com",
        roles=["customer"],
        customer_id=uuid4(),
    )
    booking = SimpleNamespace(
        id=uuid4(),
        customer_id=ctx.customer_id,
        customer_user_id=ctx.user_id,
        provider_id=uuid4(),
        status="completed",
        payment_completed=True,
    )

    async def _get(_db, _id):
        return booking

    with patch("app.core.services.payment_writes.booking_service.get_booking", _get):
        try:
            asyncio.run(refund_booking(SimpleNamespace(), ctx=ctx, booking_id=booking.id))
            raise AssertionError("expected conflict")
        except HTTPException as exc:
            assert exc.status_code == 409


def test_refund_note_is_stable_for_idempotency():
    booking_id = uuid4()
    assert refund_note(booking_id) == refund_note(booking_id)
    assert "cancel refund" in refund_note(booking_id)
