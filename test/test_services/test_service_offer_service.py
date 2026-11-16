"""Unit tests for ServiceOfferService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.service_offer_service import ServiceOfferService
from app.domain.booking import BookingDomain
from app.domain.catalog import ServiceDomain
from app.domain.exceptions import EntityConflictError, EntityNotFoundError, ValidationError
from app.domain.offer import ServiceOfferDomain


@pytest.fixture
def mock_offer_repo():
    return AsyncMock()


@pytest.fixture
def mock_service_repo():
    return AsyncMock()


@pytest.fixture
def mock_booking_repo():
    return AsyncMock()


@pytest.fixture
def offer_service(mock_offer_repo, mock_service_repo, mock_booking_repo):
    return ServiceOfferService(
        offer_repo=mock_offer_repo,
        service_repo=mock_service_repo,
        booking_repo=mock_booking_repo,
    )


@pytest.mark.asyncio
async def test_create_offer_success(offer_service, mock_offer_repo, mock_service_repo):
    cust_id = uuid4()
    prov_id = uuid4()
    srv_id = uuid4()

    mock_service_repo.get_by_id.return_value = ServiceDomain(
        id=srv_id,
        provider_id=prov_id,
        service_name="Custom Electrical Installation",
        allows_custom_offer=True,
    )
    mock_offer_repo.has_pending_offer.return_value = False
    mock_offer_repo.create_offer.return_value = ServiceOfferDomain(
        id=uuid4(),
        service_id=str(srv_id),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=800.0,
        status="pending",
    )

    payload = {
        "service_id": str(srv_id),
        "provider_id": str(prov_id),
        "offered_price": 800.0,
        "service_description": "Full home electrical wiring inspection",
        "booking_address": {"city": "Addis Ababa"},
    }
    created = await offer_service.create_offer(customer_id=cust_id, payload=payload)
    assert created.offered_price == 800.0
    mock_offer_repo.create_offer.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_offer_service_disallows_custom(
    offer_service, mock_service_repo
):
    cust_id = uuid4()
    srv_id = uuid4()

    mock_service_repo.get_by_id.return_value = ServiceDomain(
        id=srv_id,
        service_name="Fixed Standard Haircut",
        allows_custom_offer=False,
    )

    payload = {
        "service_id": str(srv_id),
        "provider_id": str(uuid4()),
        "offered_price": 500.0,
        "service_description": "Custom haircut",
        "booking_address": {"city": "Addis Ababa"},
    }
    with pytest.raises(ValidationError, match="does not allow custom pricing"):
        await offer_service.create_offer(customer_id=cust_id, payload=payload)


@pytest.mark.asyncio
async def test_create_offer_duplicate_pending(
    offer_service, mock_offer_repo, mock_service_repo
):
    cust_id = uuid4()
    srv_id = uuid4()
    prov_id = uuid4()

    mock_service_repo.get_by_id.return_value = ServiceDomain(
        id=srv_id,
        allows_custom_offer=True,
    )
    mock_offer_repo.has_pending_offer.return_value = True

    payload = {
        "service_id": str(srv_id),
        "provider_id": str(prov_id),
        "offered_price": 500.0,
        "service_description": "Inspection",
        "booking_address": {"city": "Addis Ababa"},
    }
    with pytest.raises(EntityConflictError, match="already have a pending offer"):
        await offer_service.create_offer(customer_id=cust_id, payload=payload)


@pytest.mark.asyncio
async def test_accept_and_book_creates_booking(
    offer_service, mock_offer_repo, mock_booking_repo
):
    offer_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()
    srv_id = uuid4()

    offer = ServiceOfferDomain(
        id=offer_id,
        service_id=str(srv_id),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=950.0,
        status="pending",
        service_description="Complex Plumbing Work",
        booking_address={"address": "Bole, Addis Ababa"},
    )
    mock_offer_repo.get_by_id.return_value = offer

    booking_id = uuid4()
    mock_booking_repo.upsert_booking.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_name="Complex Plumbing Work",
        price=950.0,
        total_amount=950.0,
        status="accepted",
    )

    booking = await offer_service.accept_and_book(offer_id, prov_id)
    assert booking.id == booking_id
    assert booking.status == "accepted"
    mock_booking_repo.upsert_booking.assert_awaited_once()
    mock_offer_repo.update_status.assert_awaited_once_with(offer_id, "accepted")
    mock_offer_repo.attach_booking.assert_awaited_once_with(offer_id, str(booking_id))

