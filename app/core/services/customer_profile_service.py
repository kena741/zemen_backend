"""Core service for customer profiles, allowlisted updates, and uniqueness checks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.utils.phone import normalize_ethiopian_phone
from app.domain.customer import CustomerDomain
from app.domain.exceptions import EntityConflictError, EntityNotFoundError
from app.persistence.repositories.customer_repo import CustomerRepository

CUSTOMER_ALLOWLISTED_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "user_name",
        "email",
        "country_code",
        "phone",
        "profile_pic",
        "fcm_token",
        "customer_addresses",
        "default_address",
        "address",
        "slug",
    }
)


class CustomerProfileService:
    def __init__(self, customer_repo: CustomerRepository) -> None:
        self.customer_repo = customer_repo

    async def get_profile(self, customer_id: UUID) -> CustomerDomain:
        customer = await self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise EntityNotFoundError("Customer", customer_id)
        return customer

    async def get_profile_by_user_id(self, user_id: UUID) -> CustomerDomain | None:
        return await self.customer_repo.get_by_user_id(user_id)

    async def get_profile_by_email(self, email: str) -> CustomerDomain | None:
        return await self.customer_repo.get_by_email(email)

    async def get_profile_by_phone(self, phone: str) -> CustomerDomain | None:
        return await self.customer_repo.get_by_phone(phone)

    async def is_phone_registered(self, phone: str, exclude_id: UUID | None = None) -> bool:
        return await self.customer_repo.is_phone_registered(phone, exclude_id)

    async def update_profile(self, customer_id: UUID, patch: dict[str, Any]) -> CustomerDomain:
        # Check phone uniqueness if phone is changing
        if "phone" in patch and patch["phone"]:
            norm_phone = normalize_ethiopian_phone(patch["phone"])
            if await self.is_phone_registered(norm_phone, exclude_id=customer_id):
                raise EntityConflictError(f"Phone number '{patch['phone']}' is already registered to another account.")
            patch["phone"] = norm_phone

        clean_patch = {k: v for k, v in patch.items() if k in CUSTOMER_ALLOWLISTED_FIELDS and v is not None}
        updated = await self.customer_repo.update_customer(customer_id, clean_patch)
        if not updated:
            raise EntityNotFoundError("Customer", customer_id)
        return updated

    async def update_fcm_token(self, customer_id: UUID, fcm_token: str) -> None:
        await self.customer_repo.update_fcm_token(customer_id, fcm_token)

    async def archive_profile(self, customer_id: UUID) -> CustomerDomain:
        archived = await self.customer_repo.archive(customer_id, True)
        if not archived:
            raise EntityNotFoundError("Customer", customer_id)
        return archived

