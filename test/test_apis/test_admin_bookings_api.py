"""Integration tests for Admin Bookings API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.booking import BookingDetailDomain, BookingWalletLedgerItemDomain
from .conftest import ApiTestDbSession


@pytest.fixture
def super_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


def test_list_bookings_endpoint(api_client, super_admin_context):
    booking_id = uuid4()
    mock_b = BookingDetailDomain(
        id=booking_id,
        provider_id=uuid4(),
        customer_id=uuid4(),
        service_id=uuid4(),
        service_name="Office Cleaning",
        customer_name="Dawit Bekele",
        provider_name="Provider Martha",
        price=850.0,
        total_amount=850.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=True,
        status="in_progress",
        is_archived=False,
    )

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_bookings = AsyncMock(return_value=[mock_b])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/bookings")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(booking_id)
        assert data[0]["serviceName"] == "Office Cleaning"
        assert data[0]["totalAmount"] == 850.0
        assert data[0]["paymentCompleted"] is True


def test_get_bookings_badge_count(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.count_badge = AsyncMock(return_value=7)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/bookings/badge-count")

        assert res.status_code == 200
        assert res.json() == {"count": 7}


def test_get_commission_config(api_client, super_admin_context):
    db = ApiTestDbSession()
    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/bookings/commission-config")

    assert res.status_code == 200
    data = res.json()
    assert "defaultCommissionRate" in data
    assert data["defaultCommissionRate"] == 10.0


def test_get_booking_by_id(api_client, super_admin_context):
    booking_id = uuid4()
    mock_b = BookingDetailDomain(
        id=booking_id,
        provider_id=uuid4(),
        customer_id=uuid4(),
        service_id=uuid4(),
        service_name="Dry Cleaning",
        customer_name="Sara Ahmed",
        provider_name="Provider Kebede",
        price=400.0,
        total_amount=400.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=False,
        status="pending",
        is_archived=False,
    )

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.get_booking = AsyncMock(return_value=mock_b)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get(f"/api/v1/admin/bookings/{booking_id}")

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["id"] == str(booking_id)
        assert data["serviceName"] == "Dry Cleaning"


def test_update_booking_status_endpoint(api_client, super_admin_context):
    booking_id = uuid4()
    from app.domain.booking import BookingTransitionResultDomain

    mock_res = BookingTransitionResultDomain(
        ok=True,
        status="completed",
        unchanged=False,
        provider_payout=720.0,
    )

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.update_status = AsyncMock(return_value=mock_res)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.patch(
            f"/api/v1/admin/bookings/{booking_id}/status",
            json={
                "status": "completed",
                "applyCommission": True,
                "commissionPercent": 10.0,
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["status"] == "completed"
        assert body["providerPayout"] == 720.0


def test_update_booking_note_endpoint(api_client, super_admin_context):
    booking_id = uuid4()
    mock_b = BookingDetailDomain(
        id=booking_id,
        provider_id=uuid4(),
        customer_id=uuid4(),
        service_id=uuid4(),
        service_name="Painting",
        customer_name="John Doe",
        provider_name="Paint Pros",
        price=1500.0,
        total_amount=1500.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=True,
        status="accepted",
        admin_note="Follow up tomorrow morning",
        is_archived=False,
    )

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.update_note = AsyncMock(return_value=mock_b)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.patch(
            f"/api/v1/admin/bookings/{booking_id}/note",
            json={"adminNote": "Follow up tomorrow morning"},
        )

        assert res.status_code == 200
        assert res.json()["data"]["adminNote"] == "Follow up tomorrow morning"


def test_delete_booking_endpoint(api_client, super_admin_context):
    booking_id = uuid4()

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.delete_booking = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.delete(f"/api/v1/admin/bookings/{booking_id}")

        assert res.status_code == 200
        assert res.json() == {"ok": True}


def test_initiate_and_verify_payment_endpoint(api_client, super_admin_context):
    booking_id = uuid4()

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.initiate_payment = AsyncMock(
            return_value={
                "status": "success",
                "checkout_url": "https://checkout.chapa.co/pay/123",
                "tx_ref": "bkg-12345",
                "booking_id": booking_id,
                "amount": 500.0,
            }
        )
        mock_svc.verify_payment = AsyncMock(
            return_value={
                "status": "success",
                "booking_id": str(booking_id),
                "amount": 500.0,
                "message": "Payment verified successfully",
            }
        )

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)

        # Body-based initiate payment
        res_init = client.post(
            "/api/v1/admin/bookings/payment",
            json={"bookingId": str(booking_id), "phoneNumber": "+251911000000"},
        )
        assert res_init.status_code == 200
        assert res_init.json()["checkoutUrl"] == "https://checkout.chapa.co/pay/123"

        # Body-based verify payment
        res_ver = client.post(
            "/api/v1/admin/bookings/payment/verify",
            json={"bookingId": str(booking_id)},
        )
        assert res_ver.status_code == 200
        assert res_ver.json()["status"] == "success"


def test_get_wallet_ledger_endpoint(api_client, super_admin_context):
    booking_id = uuid4()
    item = BookingWalletLedgerItemDomain(
        id=uuid4(),
        user_id=uuid4(),
        amount="450.00",
        is_credit=True,
        payment_type="payout",
        type="booking_payout",
        note="Payout for completed booking",
        created_date=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.routers.admin.bookings._get_booking_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.get_wallet_ledger = AsyncMock(return_value=[item])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get(f"/api/v1/admin/bookings/{booking_id}/wallet-ledger")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["paymentType"] == "payout"
        assert data[0]["isCredit"] is True
