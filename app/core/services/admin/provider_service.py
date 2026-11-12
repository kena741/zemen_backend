"""Service for Admin Provider management."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.auth.hashing import hash_password
from app.core.notifications.fcm import FCMService, get_fcm_service
from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.provider import (
    BankMethodDomain,
    CompanyDomain,
    ProviderDomain,
)
from app.domain.verification import DocumentDeliveryDomain
from app.persistence.repositories.document_delivery_repo import DocumentDeliveryRepository
from app.persistence.repositories.provider_bank_repo import ProviderBankRepository
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.sqlalchemy.models.identity import Provider
from app.persistence.sqlalchemy.models.users import User


def _generate_slug(base: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in base.lower()).strip("-")
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"{cleaned}-{suffix}" if cleaned else f"prov-{suffix}"


def _generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ProviderAdminService:
    def __init__(
        self,
        provider_repo: ProviderRepository,
        bank_repo: ProviderBankRepository,
        company_repo: ProviderCompanyRepository,
        delivery_repo: DocumentDeliveryRepository,
        audit_service: AdminAuditService,
        fcm_service: FCMService | None = None,
    ) -> None:
        self.provider_repo = provider_repo
        self.bank_repo = bank_repo
        self.company_repo = company_repo
        self.delivery_repo = delivery_repo
        self.audit_service = audit_service
        self.fcm_service = fcm_service or get_fcm_service()

    async def list_providers(self, include_archived: bool = True) -> list[ProviderDomain]:
        return await self.provider_repo.list_providers(include_archived=include_archived)

    async def get_provider(self, provider_id: UUID) -> ProviderDomain:
        p = await self.provider_repo.get_by_id(provider_id)
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return p

    async def count_services_by_provider(self) -> dict[str, int]:
        return await self.provider_repo.count_services_by_provider()

    async def create_provider(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        country_code: str | None = "+251",
        password: str | None = None,
        ctx: AdminContext | None = None,
    ) -> tuple[ProviderDomain, str, dict[str, Any]]:
        clean_email = email.strip().lower() if email else None
        if clean_email:
            existing = await self.provider_repo.get_by_email(clean_email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Provider with email '{clean_email}' already exists",
                )

        temp_pwd = password or _generate_temp_password()
        hashed_pwd = hash_password(temp_pwd)

        # Create linked User in users table
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        user_entity = User(
            id=user_id,
            email=clean_email,
            phone=phone,
            hashed_password=hashed_pwd,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.provider_repo.session.add(user_entity)

        # Generate unique slug
        base_name = f"{first_name or ''} {last_name or ''}".strip() or phone or "provider"
        slug = _generate_slug(base_name)
        for _ in range(25):
            slug_exists = await self.provider_repo.get_by_slug(slug)
            if not slug_exists:
                break
            slug = _generate_slug(base_name)

        provider_id = uuid4()
        provider_entity = Provider(
            id=provider_id,
            user_id=user_id,
            email=clean_email,
            first_name=first_name,
            last_name=last_name,
            user_name=f"{first_name or ''} {last_name or ''}".strip() or None,
            phone_number=phone,
            country_code=country_code,
            slug=slug,
            active=True,
            activation_paid=False,
            service_tier_max=0,
            signup_source="admin",
            provider_type="individual",
            company_verification_status="not_submitted",
            verified_subcategory_ids=[],
            social_links={},
            created_at=now,
            updated_at=now,
        )
        domain = await self.provider_repo.create(provider_entity)

        await self.audit_service.log_action(
            action="create",
            resource_type="provider",
            resource_id=str(domain.id),
            summary=f"Created provider '{domain.full_name}' ({domain.email or domain.phone_number})",
            ctx=ctx,
        )

        sms_result = {
            "sent": False,
            "recipient": phone,
            "error": "SMS gateway credentials not configured",
        }

        return domain, temp_pwd, sms_result

    async def update_provider_profile(
        self,
        provider_id: UUID,
        payload: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> ProviderDomain:
        provider = await self.get_provider(provider_id)

        update_values: dict[str, Any] = {}
        key_map = {
            "firstName": "first_name",
            "first_name": "first_name",
            "lastName": "last_name",
            "last_name": "last_name",
            "phoneNumber": "phone_number",
            "phone_number": "phone_number",
            "address": "address",
            "location": "location",
            "banner": "banner",
            "profileImage": "profile_image",
            "profile_image": "profile_image",
            "countryCode": "country_code",
            "country_code": "country_code",
            "admin_note": "admin_note",
        }

        for in_key, out_col in key_map.items():
            if in_key in payload and payload[in_key] is not None:
                update_values[out_col] = payload[in_key]

        # Sync profileBio or companyName to Company table if present
        company_updates: dict[str, Any] = {}
        if "profileBio" in payload or "profile_bio" in payload:
            company_updates["profile_bio"] = payload.get("profileBio") or payload.get("profile_bio")
        if "companyName" in payload or "company_name" in payload:
            c_name = payload.get("companyName") or payload.get("company_name")
            company_updates["company_name"] = c_name
            company_updates["name"] = c_name

        if company_updates:
            await self.company_repo.upsert_company(provider_id, company_updates)

        if update_values:
            update_values["updated_at"] = datetime.now(timezone.utc)
            updated = await self.provider_repo.update(provider_id, update_values)
            if updated:
                provider = updated

        await self.audit_service.log_action(
            action="update",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Updated profile for provider '{provider.full_name}'",
            metadata={"fields_updated": list(update_values.keys()) + list(company_updates.keys())},
            ctx=ctx,
        )

        return provider

    async def archive_provider(
        self,
        provider_id: UUID,
        action: str,
        ctx: AdminContext | None = None,
    ) -> ProviderDomain:
        should_archive = action == "archive"
        updated = await self.provider_repo.archive(provider_id, should_archive)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        act_name = "archive" if should_archive else "restore"
        await self.audit_service.log_action(
            action=act_name,
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"{act_name.capitalize()}d provider '{updated.full_name}'",
            ctx=ctx,
        )
        return updated

    async def delete_provider(
        self,
        provider_id: UUID,
        ctx: AdminContext | None = None,
    ) -> None:
        p = await self.get_provider(provider_id)
        deleted = await self.provider_repo.delete(provider_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        await self.audit_service.log_action(
            action="delete",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Deleted provider '{p.full_name}'",
            ctx=ctx,
        )

    # Bank Details
    async def get_bank_details(
        self, provider_id: UUID
    ) -> tuple[BankMethodDomain | None, list[BankMethodDomain]]:
        await self.get_provider(provider_id)
        methods = await self.bank_repo.list_for_provider(provider_id)
        default_method = next((m for m in methods if m.is_default), methods[0] if methods else None)
        return default_method, methods

    async def upsert_bank_details(
        self,
        provider_id: UUID,
        holder_name: str | None,
        account_number: str,
        bank_name: str | None,
        swift_code: str | None = None,
        branch_city: str | None = None,
        branch_country: str | None = None,
        method_code: str | None = None,
        method_id: UUID | None = None,
        ctx: AdminContext | None = None,
    ) -> BankMethodDomain:
        await self.get_provider(provider_id)
        result = await self.bank_repo.upsert_bank_details(
            provider_id=provider_id,
            holder_name=holder_name,
            account_number=account_number,
            bank_name=bank_name,
            swift_code=swift_code,
            branch_city=branch_city,
            branch_country=branch_country,
            method_code=method_code,
            method_id=method_id,
        )
        await self.audit_service.log_action(
            action="update",
            resource_type="provider_bank_details",
            resource_id=str(result.id),
            summary=f"Upserted bank details for provider {provider_id}",
            ctx=ctx,
        )
        return result

    # Company Profile
    async def get_company_profile(
        self, provider_id: UUID
    ) -> tuple[CompanyDomain | None, dict[str, Any]]:
        provider = await self.get_provider(provider_id)
        company = await self.company_repo.get_by_provider_id(provider_id)
        verification = {
            "status": provider.company_verification_status,
            "licenseUrl": provider.company_license_url,
            "rejectionReason": provider.company_rejection_reason,
        }
        return company, verification

    async def patch_company_profile(
        self,
        provider_id: UUID,
        payload: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> tuple[CompanyDomain, dict[str, Any]]:
        provider = await self.get_provider(provider_id)

        prov_updates: dict[str, Any] = {}
        if "companyVerificationStatus" in payload:
            prov_updates["company_verification_status"] = payload["companyVerificationStatus"]
        if "companyLicenseUrl" in payload:
            prov_updates["company_license_url"] = payload["companyLicenseUrl"]
        if "companyRejectionReason" in payload:
            prov_updates["company_rejection_reason"] = payload["companyRejectionReason"]

        if prov_updates:
            prov_updates["updated_at"] = datetime.now(timezone.utc)
            updated_p = await self.provider_repo.update(provider_id, prov_updates)
            if updated_p:
                provider = updated_p

        company_fields = {
            k: v
            for k, v in {
                "name": payload.get("name") or payload.get("companyName"),
                "company_name": payload.get("companyName"),
                "website": payload.get("website"),
                "industry": payload.get("industry"),
                "company_size": payload.get("companySize"),
                "headquarters": payload.get("headquarters"),
                "founded": payload.get("founded"),
                "profile_bio": payload.get("profileBio"),
                "banner_image": payload.get("bannerImage"),
            }.items()
            if v is not None
        }

        company = await self.company_repo.upsert_company(provider_id, company_fields)

        await self.audit_service.log_action(
            action="update",
            resource_type="provider_company",
            resource_id=str(provider_id),
            summary=f"Patched company profile & verification for provider {provider_id}",
            ctx=ctx,
        )

        verification = {
            "status": provider.company_verification_status,
            "licenseUrl": provider.company_license_url,
            "rejectionReason": provider.company_rejection_reason,
        }
        return company, verification

    # Push & Messaging
    async def get_push_readiness(self, provider_id: UUID) -> dict[str, Any]:
        provider = await self.get_provider(provider_id)
        has_fcm = bool(provider.fcm_token)
        has_phone = bool(provider.phone_number)
        return {
            "fcm_registered": has_fcm,
            "can_send": has_fcm,
            "reason": None if has_fcm else "Provider has no registered FCM device token",
            "name": provider.full_name,
            "sms_ready": has_phone,
            "sms_recipient": provider.phone_number,
            "debug": {
                "provider_id": str(provider_id),
                "user_id": str(provider.user_id),
                "fcm_token_preview": provider.fcm_token[:10] + "..." if provider.fcm_token else None,
            },
        }

    async def send_provider_push(
        self,
        provider_id: UUID,
        title: str,
        body: str,
        route: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.get_provider(provider_id)
        if not provider.fcm_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider has no registered FCM device token",
            )
        data = {"route": route} if route else {}
        res = await self.fcm_service.send_to_token(
            token=provider.fcm_token,
            title=title,
            body=body,
            data=data,
        )
        await self.audit_service.log_action(
            action="send_push",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Sent push notification '{title}' to provider {provider.full_name}",
            ctx=ctx,
        )
        return res

    # Document Deliveries
    async def list_document_deliveries(self, provider_id: UUID) -> list[DocumentDeliveryDomain]:
        await self.get_provider(provider_id)
        return await self.delivery_repo.list_for_recipient("provider", provider_id)

    async def send_document_delivery(
        self,
        provider_id: UUID,
        document_id: UUID,
        note: str | None = None,
        ctx: AdminContext | None = None,
    ) -> tuple[DocumentDeliveryDomain, dict[str, Any]]:
        provider = await self.get_provider(provider_id)
        admin_id = ctx.admin_id if ctx else None
        delivery = await self.delivery_repo.create_delivery(
            document_id=document_id,
            recipient_type="provider",
            recipient_id=provider_id,
            sent_by=admin_id,
        )

        push_res: dict[str, Any] = {"sent": False}
        if provider.fcm_token:
            title = "New Document Shared"
            body = f"Admin has shared '{delivery.document_title or 'a document'}' with you."
            push_res = await self.fcm_service.send_to_token(
                token=provider.fcm_token,
                title=title,
                body=body,
                data={"route": "/documents", "delivery_id": str(delivery.id)},
            )

        await self.audit_service.log_action(
            action="create",
            resource_type="document_delivery",
            resource_id=str(delivery.id),
            summary=f"Sent document '{delivery.document_title}' to provider {provider.full_name}",
            ctx=ctx,
        )
        return delivery, push_res
