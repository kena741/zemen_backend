"""Unit tests for MobileBookingService orchestration and queries."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.mobile_booking_service import MobileBookingService
from app.domain.booking import BookingDomain, MonthlyEarningsDomain
from app.domain.customer import CustomerDomain
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.domain.provider import ProviderDomain


@pytest.fixture
def mock_booking_repo():
    return AsyncMock()


@pytest.fixture
def mock_customer_repo():
    return AsyncMock()


@pytest.fixture
def mock_provider_repo():
    return AsyncMock()


@pytest.fixture
def mobile_booking_service(mock_booking_repo, mock_customer_repo, mock_provider_repo):
    return MobileBookingService(
        booking_repo=mock_booking_repo,
        customer_repo=mock_customer_repo,
        provider_repo=mock_provider_repo,
    )


@pytest.mark.asyncio
async def test_create_or_update_booking_success(mobile_booking_service, mock_booking_repo):
    user_id = uuid4()
    cust_id = uuid4()
    prov_id = uuid4()

    mock_booking_repo.upsert_booking.return_value = BookingDomain(
        id=uuid4(),
        provider_id=prov_id,
        customer_id=cust_id,
        service_name="Carpet Cleaning",
        status="pending",
    )

    payload = {
        "provider_id": prov_id,
        "service_name": "Carpet Cleaning",
        "price": 200.0,
    }

    created = await mobile_booking_service.create_or_update_booking(
        actor_user_id=user_id,
        actor_role="customer",
        payload=payload,
        actor_customer_id=cust_id,
    )

    assert created.service_name == "Carpet Cleaning"
    mock_booking_repo.upsert_booking.assert_awaited_once()
    passed_payload = mock_booking_repo.upsert_booking.call_args[0][0]
    assert passed_payload["customer_id"] == cust_id
    assert "otp" in passed_payload  # Auto-generated 6-digit OTP


@pytest.mark.asyncio
async def test_create_booking_missing_provider(mobile_booking_service):
    with pytest.raises(ValidationError, match="provider_id is required"):
        await mobile_booking_service.create_or_update_booking(
            actor_user_id=uuid4(),
            actor_role="customer",
            payload={"service_name": "No provider"},
        )


@pytest.mark.asyncio
async def test_get_booking_authorization(mobile_booking_service, mock_booking_repo):
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()
    user_id = uuid4()
    other_user_id = uuid4()

    booking = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        customer_user_id=user_id,
    )
    mock_booking_repo.get_by_id_enriched.return_value = booking

    # Authorized customer can view
    res = await mobile_booking_service.get_booking(
        booking_id=booking_id,
        actor_user_id=user_id,
        actor_role="customer",
        customer_id=cust_id,
    )
    assert res.id == booking_id

    # Unauthorized stranger cannot view
    with pytest.raises(PermissionDeniedError):
        await mobile_booking_service.get_booking(
            booking_id=booking_id,
            actor_user_id=other_user_id,
            actor_role="customer",
            customer_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_get_provider_monthly_earnings(mobile_booking_service, mock_booking_repo):
    prov_id = uuid4()
    mock_booking_repo.get_monthly_earnings.return_value = [
        MonthlyEarningsDomain(
            year=2026,
            month=10,
            month_name="October",
            total_earnings=15000.0,
            completed_bookings_count=12,
        )
    ]

    earnings = await mobile_booking_service.get_provider_monthly_earnings(prov_id, year=2026)
    assert len(earnings) == 1
    assert earnings[0].total_earnings == 15000.0
    mock_booking_repo.get_monthly_earnings.assert_awaited_once_with(
        provider_id=prov_id, year=2026
    )


@pytest.mark.asyncio
async def test_delete_unpaid_pending(mobile_booking_service, mock_booking_repo):
    booking_id = uuid4()
    cust_id = uuid4()

    mock_booking_repo.delete_unpaid_pending.return_value = True
    assert (
        await mobile_booking_service.delete_unpaid_pending(booking_id, cust_id) is True
    )

    mock_booking_repo.delete_unpaid_pending.return_value = False
    with pytest.raises(EntityNotFoundError):
        await mobile_booking_service.delete_unpaid_pending(booking_id, cust_id)

