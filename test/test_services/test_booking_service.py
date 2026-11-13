"""Unit tests for BookingAdminService."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.booking_service import BookingAdminService
from app.domain.booking import BookingDetailDomain
from app.domain.catalog import ServiceDomain
from app.domain.customer import CustomerDomain
from app.domain.provider import ProviderDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.booking_admin_repo import BookingAdminRepository
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from .conftest import ServiceMockSession


@pytest.fixture
def mock_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.fixture
def booking_service():
    session = ServiceMockSession()
    bkg_repo = BookingAdminRepository(session)  # type: ignore[arg-type]
    prov_repo = ProviderRepository(session)  # type: ignore[arg-type]
    cust_repo = CustomerRepository(session)  # type: ignore[arg-type]
    srv_repo = ServiceRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    fcm_mock = MagicMock()
    fcm_mock.send_to_token = AsyncMock(return_value={"sent": True, "message_id": "msg-booking-123"})

    service = BookingAdminService(
        booking_repo=bkg_repo,
        provider_repo=prov_repo,
        customer_repo=cust_repo,
        service_repo=srv_repo,
        audit_service=audit_service,
        fcm_service=fcm_mock,
    )
    return service, bkg_repo, prov_repo, cust_repo, srv_repo, fcm_mock, session


@pytest.mark.asyncio
async def test_create_booking_pay_later(booking_service, mock_context):
    service, bkg_repo, prov_repo, cust_repo, srv_repo, _, session = booking_service
    prov_id = uuid4()
    cust_id = uuid4()
    srv_id = uuid4()
    booking_id = uuid4()

    prov_repo.get_by_id = AsyncMock(
        return_value=ProviderDomain(
            id=prov_id,
            user_id=uuid4(),
            first_name="Test",
            last_name="Provider",
            email="prov@example.com",
            phone_number="+251911111111",
        )
    )
    cust_repo.get_by_id = AsyncMock(
        return_value=CustomerDomain(
            id=cust_id,
            user_id=uuid4(),
            first_name="Test",
            last_name="Customer",
            email="cust@example.com",
            phone="+251922222222",
            wallet_amount=Decimal("500.00"),
        )
    )
    srv_repo.get_by_id = AsyncMock(
        return_value=ServiceDomain(
            id=srv_id,
            service_name="House Cleaning",
            provider_id=prov_id,
            category_id=uuid4(),
            sub_category_id=uuid4(),
            price=300.0,
            active=True,
        )
    )

    created_booking = BookingDetailDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_id=srv_id,
        service_name="House Cleaning",
        customer_name="Test Customer",
        customer_phone="+251922222222",
        customer_email="cust@example.com",
        provider_name="Test Provider",
        price=300.0,
        total_amount=300.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=False,
        status="pending",
        is_archived=False,
    )
    bkg_repo.get_by_id_enriched = AsyncMock(return_value=created_booking)

    result = await service.create_booking(
        provider_id=prov_id,
        service_id=srv_id,
        customer_id=cust_id,
        booking_date=datetime.now(timezone.utc),
        quantity=1,
        payment_path="pay_later",
        ctx=mock_context,
    )

    assert result.id == booking_id
    assert result.total_amount == 300.0
    assert result.status == "pending"
    assert len(session.added) >= 2  # BookedService + Payment (+ AdminActivityLog)


@pytest.mark.asyncio
async def test_create_booking_wallet_insufficient_balance(booking_service, mock_context):
    service, _, prov_repo, cust_repo, srv_repo, _, _ = booking_service
    prov_id = uuid4()
    cust_id = uuid4()
    srv_id = uuid4()

    prov_repo.get_by_id = AsyncMock(
        return_value=ProviderDomain(
            id=prov_id,
            user_id=uuid4(),
            first_name="Test",
            last_name="Provider",
            email="prov@example.com",
        )
    )
    cust_repo.get_by_id = AsyncMock(
        return_value=CustomerDomain(
            id=cust_id,
            user_id=uuid4(),
            first_name="Poor",
            last_name="Customer",
            phone="+251911223344",
            wallet_amount=Decimal("50.00"),  # Less than service price
        )
    )
    srv_repo.get_by_id = AsyncMock(
        return_value=ServiceDomain(
            id=srv_id,
            service_name="Car Repair",
            provider_id=prov_id,
            category_id=uuid4(),
            sub_category_id=uuid4(),
            price=1500.0,
            active=True,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_booking(
            provider_id=prov_id,
            service_id=srv_id,
            customer_id=cust_id,
            booking_date=datetime.now(timezone.utc),
            quantity=1,
            payment_path="wallet",
            ctx=mock_context,
        )

    assert exc_info.value.status_code == 400
    assert "Insufficient wallet balance" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_status_completed_with_commission(booking_service, mock_context):
    service, bkg_repo, prov_repo, cust_repo, _, fcm_mock, session = booking_service
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()

    existing_booking = BookingDetailDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_id=uuid4(),
        service_name="Plumbing Fix",
        customer_name="Abebe",
        provider_name="Provider Kebede",
        price=1000.0,
        total_amount=1000.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=True,
        status="in_progress",
        is_archived=False,
    )
    bkg_repo.get_by_id_enriched = AsyncMock(return_value=existing_booking)
    bkg_repo.update_status = AsyncMock(return_value=True)

    prov_repo.get_by_id = AsyncMock(
        return_value=ProviderDomain(
            id=prov_id,
            user_id=uuid4(),
            first_name="Kebede",
            last_name="Tadesse",
            email="kebede@example.com",
            wallet_amount=Decimal("200.00"),
            fcm_token="prov_fcm_token_123",
        )
    )
    prov_repo.update = AsyncMock(return_value=True)

    cust_repo.get_by_id = AsyncMock(
        return_value=CustomerDomain(
            id=cust_id,
            user_id=uuid4(),
            first_name="Abebe",
            last_name="Bikila",
            phone="+251911444444",
            fcm_token="cust_fcm_token_456",
        )
    )

    result = await service.update_status(
        booking_id=booking_id,
        new_status="completed",
        apply_commission=True,
        commission_percent=10.0,
        notify_provider=True,
        notify_customer=True,
        ctx=mock_context,
    )

    assert result.ok is True
    assert result.status == "completed"
    assert result.unchanged is False
    assert result.provider_payout == 900.0  # 1000 - 10% (100) = 900
    # FCM dispatched to both provider and customer
    assert fcm_mock.send_to_token.call_count == 2


@pytest.mark.asyncio
async def test_update_status_rejected_with_customer_refund(booking_service, mock_context):
    service, bkg_repo, prov_repo, cust_repo, _, _, session = booking_service
    booking_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()

    existing_booking = BookingDetailDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_id=uuid4(),
        service_name="Electrical Fix",
        customer_name="Almaz",
        provider_name="Provider Dawit",
        price=500.0,
        total_amount=500.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=True,
        status="pending",
        is_archived=False,
    )
    bkg_repo.get_by_id_enriched = AsyncMock(return_value=existing_booking)
    bkg_repo.update_status = AsyncMock(return_value=True)

    cust_repo.get_by_id = AsyncMock(
        return_value=CustomerDomain(
            id=cust_id,
            user_id=uuid4(),
            first_name="Almaz",
            last_name="Ayele",
            phone="+251911555555",
            wallet_amount=Decimal("100.00"),
        )
    )
    cust_repo.update = AsyncMock(return_value=True)

    result = await service.update_status(
        booking_id=booking_id,
        new_status="rejected",
        notify_provider=False,
        notify_customer=False,
        ctx=mock_context,
    )

    assert result.ok is True
    assert result.status == "rejected"
    assert result.customer_refund == 500.0
    cust_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_note_success(booking_service, mock_context):
    service, bkg_repo, _, _, _, _, _ = booking_service
    booking_id = uuid4()

    booking = BookingDetailDomain(
        id=booking_id,
        provider_id=uuid4(),
        customer_id=uuid4(),
        service_id=uuid4(),
        service_name="Cleaning",
        customer_name="Customer",
        provider_name="Provider",
        price=200.0,
        total_amount=200.0,
        quantity=1,
        booking_date=datetime.now(timezone.utc),
        payment_completed=False,
        status="pending",
        admin_note="Urgent customer call handled",
        is_archived=False,
    )
    bkg_repo.update_note = AsyncMock(return_value=True)
    bkg_repo.get_by_id_enriched = AsyncMock(return_value=booking)

    result = await service.update_note(booking_id, "Urgent customer call handled", ctx=mock_context)
    assert result.admin_note == "Urgent customer call handled"
