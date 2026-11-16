"""Unit tests for BookingLifecycleService state machine and actions."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.booking_lifecycle_service import BookingLifecycleService
from app.domain.booking import BookingDomain
from app.domain.exceptions import (
    EntityNotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)
from app.domain.provider import HandymanDomain


@pytest.fixture
def mock_booking_repo():
    return AsyncMock()


@pytest.fixture
def mock_handyman_repo():
    return AsyncMock()


@pytest.fixture
def lifecycle_service(mock_booking_repo, mock_handyman_repo):
    return BookingLifecycleService(
        booking_repo=mock_booking_repo,
        handyman_repo=mock_handyman_repo,
    )


@pytest.mark.asyncio
async def test_provider_accept_booking(lifecycle_service, mock_booking_repo):
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()

    booking = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        status="pending",
    )
    mock_booking_repo.get_by_id.return_value = booking
    mock_booking_repo.update_booking_fields.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        status="accepted",
    )

    res = await lifecycle_service.transition_status(
        booking_id=booking_id,
        actor_role="provider",
        actor_id=prov_id,
        new_status="accepted",
    )
    assert res.status == "accepted"
    mock_booking_repo.update_booking_fields.assert_awaited_once_with(
        booking_id, {"status": "accepted"}
    )


@pytest.mark.asyncio
async def test_provider_invalid_transition(lifecycle_service, mock_booking_repo):
    booking_id = uuid4()
    prov_id = uuid4()

    booking = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        status="pending",
    )
    mock_booking_repo.get_by_id.return_value = booking

    # Provider cannot jump from pending directly to completed
    with pytest.raises(StateTransitionError):
        await lifecycle_service.transition_status(
            booking_id=booking_id,
            actor_role="provider",
            actor_id=prov_id,
            new_status="completed",
        )


@pytest.mark.asyncio
async def test_completion_with_otp_verification(lifecycle_service, mock_booking_repo):
    booking_id = uuid4()
    prov_id = uuid4()

    booking = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        status="on_going",
        otp="123456",
    )
    mock_booking_repo.get_by_id.return_value = booking
    mock_booking_repo.update_booking_fields.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        status="completed",
        payment_completed=True,
    )

    # Invalid OTP fails
    with pytest.raises(ValidationError, match="Invalid or missing completion OTP"):
        await lifecycle_service.transition_status(
            booking_id=booking_id,
            actor_role="provider",
            actor_id=prov_id,
            new_status="completed",
            otp="999999",
        )

    # Valid OTP succeeds
    res = await lifecycle_service.transition_status(
        booking_id=booking_id,
        actor_role="provider",
        actor_id=prov_id,
        new_status="completed",
        otp="123456",
    )
    assert res.status == "completed"


@pytest.mark.asyncio
async def test_assign_handyman(lifecycle_service, mock_booking_repo, mock_handyman_repo):
    booking_id = uuid4()
    prov_id = uuid4()
    hm_id = uuid4()

    booking = BookingDomain(id=booking_id, provider_id=prov_id, status="accepted")
    mock_booking_repo.get_by_id.return_value = booking
    mock_handyman_repo.get_by_id.return_value = HandymanDomain(
        id=hm_id,
        provider_id=prov_id,
        first_name="Dawit",
        last_name="Bekele",
    )
    mock_booking_repo.update_booking_fields.return_value = BookingDomain(
        id=booking_id, provider_id=prov_id, handyman_id=hm_id
    )

    res = await lifecycle_service.assign_handyman(booking_id, prov_id, hm_id)
    assert res.handyman_id == hm_id


@pytest.mark.asyncio
async def test_assign_unowned_handyman_fails(
    lifecycle_service, mock_booking_repo, mock_handyman_repo
):
    booking_id = uuid4()
    prov_id = uuid4()
    other_prov = uuid4()
    hm_id = uuid4()

    booking = BookingDomain(id=booking_id, provider_id=prov_id, status="accepted")
    mock_booking_repo.get_by_id.return_value = booking
    # Handyman belongs to a different provider
    mock_handyman_repo.get_by_id.return_value = HandymanDomain(
        id=hm_id,
        provider_id=other_prov,
        first_name="Dawit",
        last_name="Bekele",
    )

    with pytest.raises(EntityNotFoundError):
        await lifecycle_service.assign_handyman(booking_id, prov_id, hm_id)


@pytest.mark.asyncio
async def test_refund_on_decline_idempotency(lifecycle_service, mock_booking_repo):
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()

    booking = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        status="declined",
        total_amount=500.0,
    )
    mock_booking_repo.get_by_id.return_value = booking

    # First call: not yet refunded
    mock_booking_repo.has_refund_transaction.return_value = False
    mock_booking_repo.get_escrow_amount.return_value = Decimal("500.00")

    result = await lifecycle_service.refund_on_decline(booking_id, prov_id)
    assert result["status"] == "success"
    assert result["refunded_amount"] == 500.0
    mock_booking_repo.credit_customer_wallet_refund.assert_awaited_once()

    # Second call: already refunded
    mock_booking_repo.has_refund_transaction.return_value = True
    result_idem = await lifecycle_service.refund_on_decline(booking_id, prov_id)
    assert result_idem["status"] == "already_refunded"

