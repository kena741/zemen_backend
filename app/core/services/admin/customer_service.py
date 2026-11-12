"""Service for Admin Customer management and actions."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.auth.hashing import hash_password
from app.core.notifications.fcm import FCMService, get_fcm_service
from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.customer import (
    CustomerDomain,
    CustomerJobRequestItemDomain,
    CustomerStatsDomain,
)
from app.domain.provider import ProviderBookingHistoryItemDomain, ProviderDomain
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from app.persistence.sqlalchemy.models.identity import Customer, Provider
from app.persistence.sqlalchemy.models.users import User


def _generate_slug(base: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in base.lower()).strip("-")
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"{cleaned}-{suffix}" if cleaned else f"cust-{suffix}"


def _generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class CustomerAdminService:
    def __init__(
        self,
        customer_repo: CustomerRepository,
        provider_repo: ProviderRepository,
        audit_service: AdminAuditService,
        fcm_service: FCMService | None = None,
    ) -> None:
        self.customer_repo = customer_repo
        self.provider_repo = provider_repo
        self.audit_service = audit_service
        self.fcm_service = fcm_service or get_fcm_service()

    async def list_customers(self, include_archived: bool = True) -> list[CustomerDomain]:
        return await self.customer_repo.list_customers(include_archived=include_archived)

    async def list_by_provider(self, provider_id: UUID) -> list[CustomerDomain]:
        return await self.customer_repo.list_by_provider_id(provider_id)

    async def get_customer(self, customer_id: UUID) -> tuple[CustomerDomain, CustomerStatsDomain]:
        c = await self.customer_repo.get_by_id(customer_id)
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        stats = await self.customer_repo.get_stats(customer_id)
        return c, stats

    async def create_customer(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        email: str | None = None,
        country_code: str | None = "+251",
        password: str | None = None,
        ctx: AdminContext | None = None,
    ) -> tuple[CustomerDomain, str, dict[str, Any]]:
        clean_email = email.strip().lower() if email else None
        clean_phone = "".join(ch for ch in phone if ch.isdigit() or ch == "+")

        if clean_email:
            existing = await self.customer_repo.get_by_email(clean_email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Customer with email '{clean_email}' already exists",
                )

        existing_phone = await self.customer_repo.get_by_phone(clean_phone)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with phone '{clean_phone}' already exists",
            )

        temp_pwd = password or _generate_temp_password()
        hashed_pwd = hash_password(temp_pwd)

        user_id = uuid4()
        now = datetime.now(timezone.utc)
        user_entity = User(
            id=user_id,
            email=clean_email,
            phone=clean_phone,
            hashed_password=hashed_pwd,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.customer_repo.session.add(user_entity)

        base_name = f"{first_name} {last_name}".strip()
        slug = _generate_slug(base_name)
        for _ in range(25):
            slug_exists = await self.customer_repo.get_by_slug(slug)
            if not slug_exists:
                break
            slug = _generate_slug(base_name)

        customer_id = uuid4()
        customer_entity = Customer(
            id=customer_id,
            user_id=user_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone=clean_phone,
            email=clean_email,
            country_code=country_code,
            user_name=base_name,
            slug=slug,
            active=True,
            wallet_amount=Decimal("0.0"),
            signup_source="admin",
            created_at=now,
            updated_at=now,
        )
        domain = await self.customer_repo.create(customer_entity)

        await self.audit_service.log_action(
            action="create",
            resource_type="customer",
            resource_id=str(domain.id),
            summary=f"Created customer '{domain.full_name}' ({domain.phone})",
            ctx=ctx,
        )

        sms_result = {
            "sent": False,
            "recipient": clean_phone,
            "error": "SMS gateway credentials not configured",
        }

        return domain, temp_pwd, sms_result

    async def update_customer_note(
        self,
        customer_id: UUID,
        admin_note: str | None,
        ctx: AdminContext | None = None,
    ) -> CustomerDomain:
        updated = await self.customer_repo.update_note(customer_id, admin_note)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        await self.audit_service.log_action(
            action="update",
            resource_type="customer.note",
            resource_id=str(customer_id),
            summary=f"Updated admin note for customer '{updated.full_name}'",
            ctx=ctx,
        )
        return updated

    async def archive_customer(
        self,
        customer_id: UUID,
        action: str,
        ctx: AdminContext | None = None,
    ) -> CustomerDomain:
        should_archive = action == "archive"
        updated = await self.customer_repo.archive(customer_id, should_archive)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        act_name = "archive" if should_archive else "restore"
        await self.audit_service.log_action(
            action=act_name,
            resource_type="customer",
            resource_id=str(customer_id),
            summary=f"{act_name.capitalize()}d customer '{updated.full_name}'",
            ctx=ctx,
        )
        return updated

    async def delete_customer(
        self,
        customer_id: UUID,
        ctx: AdminContext | None = None,
    ) -> None:
        c, _ = await self.get_customer(customer_id)
        deleted = await self.customer_repo.delete(customer_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        await self.audit_service.log_action(
            action="delete",
            resource_type="customer",
            resource_id=str(customer_id),
            summary=f"Deleted customer '{c.full_name}'",
            ctx=ctx,
        )

    async def convert_to_provider(
        self,
        customer_id: UUID,
        ctx: AdminContext | None = None,
    ) -> ProviderDomain:
        customer, _ = await self.get_customer(customer_id)

        # Check if provider already exists for this email or user_id
        if customer.email:
            existing_p = await self.provider_repo.get_by_email(customer.email)
            if existing_p:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Provider profile already exists for this customer",
                )

        now = datetime.now(timezone.utc)
        user_id = customer.user_id or uuid4()
        prov_id = uuid4()
        slug = _generate_slug(customer.full_name)

        provider_entity = Provider(
            id=prov_id,
            user_id=user_id,
            email=customer.email,
            first_name=customer.first_name,
            last_name=customer.last_name,
            user_name=customer.full_name,
            phone_number=customer.phone,
            country_code=customer.country_code or "+251",
            slug=slug,
            active=True,
            activation_paid=False,
            service_tier_max=0,
            signup_source="converted_from_customer",
            provider_type="individual",
            company_verification_status="not_submitted",
            verified_subcategory_ids=[],
            social_links={},
            created_at=now,
            updated_at=now,
        )
        provider_domain = await self.provider_repo.create(provider_entity)

        await self.audit_service.log_action(
            action="convert_to_provider",
            resource_type="customer",
            resource_id=str(customer_id),
            summary=f"Converted customer '{customer.full_name}' into provider '{provider_domain.full_name}'",
            metadata={"new_provider_id": str(provider_domain.id)},
            ctx=ctx,
        )
        return provider_domain

    async def list_customer_bookings(
        self,
        customer_id: UUID,
    ) -> list[ProviderBookingHistoryItemDomain]:
        customer, _ = await self.get_customer(customer_id)
        from sqlalchemy import select

        stmt = (
            select(BookedService)
            .where(
                BookedService.customer_id == customer_id,
                BookedService.is_archived.is_(False),
            )
            .order_by(BookedService.created_at.desc())
        )
        res = await self.customer_repo.session.execute(stmt)
        entities = res.scalars().all()
        return [
            ProviderBookingHistoryItemDomain(
                id=e.id,
                service_name=e.service_name,
                status=e.status,
                payment_status=e.payment_status,
                payment_completed=e.payment_completed,
                amount=float(e.total_amount or e.price or 0),
                created_at=e.created_at,
                booking_date=e.booking_date,
                customer_id=e.customer_id,
                customer_name=customer.full_name,
                note=e.description,
                follow_up=e.admin_note,
            )
            for e in entities
        ]

    async def list_customer_job_requests(
        self,
        customer_id: UUID,
    ) -> list[CustomerJobRequestItemDomain]:
        await self.get_customer(customer_id)
        return await self.customer_repo.list_job_requests(customer_id)

    async def resolve_booker(self) -> CustomerDomain:
        booker = await self.customer_repo.resolve_booker()
        if not booker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No default admin booker customer available",
            )
        return booker

    async def get_push_readiness(self, customer_id: UUID) -> dict[str, Any]:
        c, _ = await self.get_customer(customer_id)
        has_fcm = bool(c.fcm_token)
        has_phone = bool(c.phone)
        return {
            "fcm_registered": has_fcm,
            "can_send": has_fcm,
            "reason": None if has_fcm else "Customer has no registered FCM device token",
            "name": c.full_name,
            "sms_ready": has_phone,
            "sms_recipient": c.phone,
            "debug": {
                "customer_id": str(customer_id),
                "user_id": str(c.user_id) if c.user_id else None,
            },
        }

    async def send_customer_push(
        self,
        customer_id: UUID,
        title: str,
        body: str,
        route: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        c, _ = await self.get_customer(customer_id)
        if not c.fcm_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer has no registered FCM device token",
            )
        data = {"route": route} if route else {}
        res = await self.fcm_service.send_to_token(
            token=c.fcm_token,
            title=title,
            body=body,
            data=data,
        )
        await self.audit_service.log_action(
            action="send_push",
            resource_type="customer",
            resource_id=str(customer_id),
            summary=f"Sent push notification '{title}' to customer {c.full_name}",
            ctx=ctx,
        )
        return res

