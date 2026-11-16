"""Integration tests for Mobile Booking endpoints (setOrder, lifecycle transitions, earnings)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.bookings import (
    get_booking_lifecycle_service,
    get_mobile_booking_service,
    get_recurring_booking_service,
)
from app.core.security.deps import AuthContext
from app.domain.booking import BookingDomain, MonthlyEarningsDomain


@pytest.fixture
def mock_booking_service():
    return AsyncMock()


@pytest.fixture
def mock_lifecycle_service():
    return AsyncMock()


@pytest.fixture
def mock_recurring_service():
    return AsyncMock()


def test_customer_list_bookings(api_client, mock_booking_service):
    user_id = uuid4()
    cust_id = uuid4()
    prov_id = uuid4()

    mock_booking_service.list_customer_bookings.return_value = [
        BookingDomain(
            id=uuid4(),
            provider_id=prov_id,
            customer_id=cust_id,
            service_name="AC Repair",
            booking_date=datetime.now(timezone.utc),
            status="pending",
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_mobile_booking_service] = lambda: mock_booking_service

    res = client.get("/api/v1/bookings")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["serviceName"] == "AC Repair"


def test_set_order_dual_casing(api_client, mock_booking_service):
    user_id = uuid4()
    cust_id = uuid4()
    prov_id = uuid4()
    booking_id = uuid4()

    mock_booking_service.create_or_update_booking.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_name="Plumbing",
        price=150.0,
        total_amount=150.0,
        status="pending",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_mobile_booking_service] = lambda: mock_booking_service

    # Submitting camelCase keys matching Flutter BookingModel.toJson()
    payload = {
        "providerId": str(prov_id),
        "serviceName": "Plumbing",
        "price": 150.0,
        "totalAmount": 150.0,
        "bookingDate": datetime.now(timezone.utc).isoformat(),
        "paymentCompleted": False,
        "taxList": [{"name": "VAT", "amount": 22.5}],
    }
    res = client.post("/api/v1/bookings", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["serviceName"] == "Plumbing"
    assert data["providerId"] == str(prov_id)


def test_provider_list_bookings_and_earnings(api_client, mock_booking_service):
    user_id = uuid4()
    prov_id = uuid4()

    mock_booking_service.list_provider_bookings.return_value = [
        BookingDomain(
            id=uuid4(),
            provider_id=prov_id,
            service_name="House Cleaning",
            status="accepted",
        )
    ]
    mock_booking_service.get_provider_monthly_earnings.return_value = [
        MonthlyEarningsDomain(
            year=2026,
            month=11,
            month_name="November",
            total_earnings=8500.0,
            completed_bookings_count=7,
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_mobile_booking_service] = lambda: mock_booking_service

    # Provider bookings list
    res = client.get("/api/v1/bookings/provider?isUpcoming=true")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    # Monthly earnings
    res_earn = client.get("/api/v1/bookings/provider/earnings/monthly")
    assert res_earn.status_code == 200
    assert len(res_earn.json()) == 1
    assert res_earn.json()[0]["totalEarnings"] == 8500.0


def test_provider_accept_and_decline_booking(api_client, mock_lifecycle_service):
    user_id = uuid4()
    prov_id = uuid4()
    booking_id = uuid4()

    mock_lifecycle_service.transition_status.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        status="accepted",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_booking_lifecycle_service] = (
        lambda: mock_lifecycle_service
    )

    # Accept
    res_acc = client.post(f"/api/v1/bookings/{booking_id}/accept")
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "accepted"

    # Decline
    mock_lifecycle_service.transition_status.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        status="declined",
        reason="Unavailable at requested time",
    )
    res_dec = client.post(
        f"/api/v1/bookings/{booking_id}/decline",
        json={"reason": "Unavailable at requested time"},
    )
    assert res_dec.status_code == 200
    assert res_dec.json()["status"] == "declined"


def test_customer_cancel_booking(api_client, mock_lifecycle_service):
    user_id = uuid4()
    cust_id = uuid4()
    booking_id = uuid4()

    mock_lifecycle_service.transition_status.return_value = BookingDomain(
        id=booking_id,
        provider_id=uuid4(),
        customer_id=cust_id,
        status="cancelled",
        reason="Plans changed",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_booking_lifecycle_service] = (
        lambda: mock_lifecycle_service
    )

    res = client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json={"reason": "Plans changed"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_verify_otp_and_service_proof(api_client, mock_lifecycle_service):
    booking_id = uuid4()
    prov_id = uuid4()

    mock_lifecycle_service.verify_otp.return_value = True
    mock_lifecycle_service.update_service_proof.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        service_proof={"start_proof": "http://img1.jpg"},
    )

    ctx = AuthContext(
        user_id=uuid4(),
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_booking_lifecycle_service] = (
        lambda: mock_lifecycle_service
    )

    # Verify OTP
    res_otp = client.post(
        f"/api/v1/bookings/{booking_id}/verify-otp",
        json={"otp": "123456"},
    )
    assert res_otp.status_code == 200
    assert res_otp.json()["valid"] is True

    # Service proof
    res_proof = client.post(
        f"/api/v1/bookings/{booking_id}/service-proof",
        json={"serviceProof": {"start_proof": "http://img1.jpg"}},
    )
    assert res_proof.status_code == 200
    assert res_proof.json()["serviceProof"]["start_proof"] == "http://img1.jpg"


def test_refund_on_decline_and_recurring_scan(
    api_client, mock_lifecycle_service, mock_recurring_service
):
    booking_id = uuid4()
    prov_id = uuid4()

    mock_lifecycle_service.refund_on_decline.return_value = {
        "status": "success",
        "refunded_amount": 500.0,
    }
    mock_recurring_service.scan_and_notify_due_cycles.return_value = 3

    ctx = AuthContext(
        user_id=uuid4(),
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_booking_lifecycle_service] = (
        lambda: mock_lifecycle_service
    )
    client.app.dependency_overrides[get_recurring_booking_service] = (
        lambda: mock_recurring_service
    )

    # Refund on decline
    res_ref = client.post(f"/api/v1/bookings/{booking_id}/refund-on-decline")
    assert res_ref.status_code == 200
    assert res_ref.json()["refunded_amount"] == 500.0

    # Recurring scan
    res_scan = client.post("/api/v1/bookings/recurring-cycle-due/scan")
    assert res_scan.status_code == 200
    assert res_scan.json()["flagged_count"] == 3

