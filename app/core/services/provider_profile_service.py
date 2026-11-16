"""Core service for provider profiles, allowlisted updates, and company metadata."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.utils.phone import normalize_ethiopian_phone
from app.domain.exceptions import EntityNotFoundError
from app.domain.provider import CompanyDomain, ProviderDomain
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository

PROVIDER_ALLOWLISTED_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "user_name",
        "phone_number",
        "email",
        "profile_image",
        "banner",
        "address",
        "country",
        "country_code",
        "currency",
        "location",
        "social_links",
        "fcm_token",
        "slug",
    }
)


class ProviderProfileService:
    def __init__(
        self,
        provider_repo: ProviderRepository,
        company_repo: ProviderCompanyRepository,
    ) -> None:
        self.provider_repo = provider_repo
        self.company_repo = company_repo

    async def get_profile(self, provider_id: UUID) -> ProviderDomain:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise EntityNotFoundError("Provider", provider_id)
        return provider

    async def get_profile_by_user_id(self, user_id: UUID) -> ProviderDomain | None:
        return await self.provider_repo.get_by_user_id(user_id)

    async def get_profile_by_email(self, email: str) -> ProviderDomain | None:
        return await self.provider_repo.get_by_email(email)

    async def get_profile_by_phone(self, phone: str) -> ProviderDomain | None:
        return await self.provider_repo.get_by_phone(phone)

    async def resolve_provider_id(self, user_id: UUID) -> UUID:
        provider = await self.provider_repo.get_by_user_id(user_id)
        if not provider:
            raise EntityNotFoundError("Provider linked to user", user_id)
        return provider.id

    async def update_profile(self, provider_id: UUID, patch: dict[str, Any]) -> ProviderDomain:
        if "phone_number" in patch and patch["phone_number"]:
            patch["phone_number"] = normalize_ethiopian_phone(patch["phone_number"])

        clean_patch = {k: v for k, v in patch.items() if k in PROVIDER_ALLOWLISTED_FIELDS and v is not None}
        updated = await self.provider_repo.update_provider(provider_id, clean_patch)
        if not updated:
            raise EntityNotFoundError("Provider", provider_id)
        return updated

    async def update_fcm_token(self, provider_id: UUID, fcm_token: str) -> None:
        await self.provider_repo.update_fcm_token(provider_id, fcm_token)

    async def archive_profile(self, provider_id: UUID) -> ProviderDomain:
        archived = await self.provider_repo.archive(provider_id, True)
        if not archived:
            raise EntityNotFoundError("Provider", provider_id)
        return archived

    async def get_company(self, provider_id: UUID) -> CompanyDomain | None:
        return await self.company_repo.get_by_provider_id(provider_id)

    async def upsert_company(self, provider_id: UUID, values: dict[str, Any]) -> CompanyDomain:
        return await self.company_repo.upsert_company(provider_id, values)

