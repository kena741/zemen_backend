"""Unit and mapping tests for BookingAdminRepository."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.booking_admin_repo import BookingAdminRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_booking_repo_to_domain():
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()
    srv_id = uuid4()

    entity = BookedService(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_id=srv_id,
        service_name="Sofa Deep Cleaning",
        first_name="Abebe",
        last_name="Kebede",
        phone_number="+251911000000",
        email="abebe@example.com",
        price=Decimal("1200.00"),
        total_amount=Decimal("1200.00"),
        quantity=1,
        status="pending",
        payment_completed=False,
        is_archived=False,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = BookingAdminRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(
        entity,
        customer_name="Abebe Kebede",
        provider_name="Provider Haile",
        service_title="Sofa Deep Cleaning",
    )

    assert domain.id == booking_id
    assert domain.provider_id == prov_id
    assert domain.customer_id == cust_id
    assert domain.customer_name == "Abebe Kebede"
    assert domain.provider_name == "Provider Haile"
    assert domain.service_name == "Sofa Deep Cleaning"
    assert domain.price == 1200.0
    assert domain.total_amount == 1200.0
    assert domain.status == "pending"
    assert domain.payment_completed is False


@pytest.mark.asyncio
async def test_booking_repo_update_status():
    booking_id = uuid4()
    mock_entity = BookedService(id=booking_id, status="completed")
    session = RepoMockSession(scalar_one_or_none_value=mock_entity)
    repo = BookingAdminRepository(session)  # type: ignore[arg-type]

    res = await repo.update_status(booking_id, "completed", admin_commission=120.0)
    assert res is not None
    assert len(session.executed_statements) == 1


@pytest.mark.asyncio
async def test_booking_repo_update_note():
    booking_id = uuid4()
    mock_entity = BookedService(id=booking_id, admin_note="Customer requested rescheduled time")
    session = RepoMockSession(scalar_one_or_none_value=mock_entity)
    repo = BookingAdminRepository(session)  # type: ignore[arg-type]

    res = await repo.update_note(booking_id, "Customer requested rescheduled time")
    assert res is not None
    assert len(session.executed_statements) == 1


@pytest.mark.asyncio
async def test_booking_repo_mark_payment_completed():
    booking_id = uuid4()
    mock_entity = BookedService(id=booking_id, payment_completed=True)
    session = RepoMockSession(scalar_one_or_none_value=mock_entity)
    repo = BookingAdminRepository(session)  # type: ignore[arg-type]

    res = await repo.mark_payment_completed(booking_id, payment_method="chapa")
    assert res is not None
    assert len(session.executed_statements) >= 1


@pytest.mark.asyncio
async def test_booking_repo_delete_cascade():
    booking_id = uuid4()
    session = RepoMockSession()
    repo = BookingAdminRepository(session)  # type: ignore[arg-type]

    res = await repo.delete_booking_cascade(booking_id)
    assert res is True
    assert len(session.executed_statements) == 3  # notification, payment, booked_service
