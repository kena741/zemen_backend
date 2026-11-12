"""Core service for Admin Platform Configuration and Settings."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.settings import (
    AppSettingDomain,
    CouponDomain,
    LanguageDomain,
    MobileAppConfigDomain,
    NavActionCountsDomain,
)
from app.persistence.repositories.app_settings_repo import AppSettingsRepository
from app.persistence.repositories.coupon_repo import CouponRepository
from app.persistence.repositories.language_repo import LanguageRepository
from app.persistence.repositories.mobile_app_config_repo import MobileAppConfigRepository
from app.persistence.repositories.nav_action_counts_repo import NavActionCountsRepository


# Mapping between frontend camelCase payload keys and DB section ids
SECTION_KEYS: dict[str, list[str]] = {
    "appSettings": ["settings", "appSettings"],
    "generalSettings": ["general", "generalSettings"],
    "policySettings": ["policy", "policySettings"],
    "paymentSettings": ["payment", "paymentSettings"],
    "contactUs": ["contact_us", "contactUs"],
    "adminCommission": ["admin_commission", "adminCommission"],
    "statusOptions": ["status", "statusOptions"],
    "constants": ["constant", "constants"],
}


class SettingsAdminService:
    def __init__(
        self,
        app_settings_repo: AppSettingsRepository,
        language_repo: LanguageRepository,
        mobile_config_repo: MobileAppConfigRepository,
        coupon_repo: CouponRepository,
        nav_action_counts_repo: NavActionCountsRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.app_settings_repo = app_settings_repo
        self.language_repo = language_repo
        self.mobile_config_repo = mobile_config_repo
        self.coupon_repo = coupon_repo
        self.nav_action_counts_repo = nav_action_counts_repo
        self.audit_service = audit_service

    # --- Platform App Settings ---

    async def get_settings(self) -> dict[str, Any]:
        all_rows = await self.app_settings_repo.list_all_settings()
        row_map: dict[str, Any] = {r.id: r.data for r in all_rows}

        languages = await self.language_repo.list_languages()

        # Build response resolving aliases
        def _get_section(keys: list[str], default: Any) -> Any:
            for k in keys:
                if k in row_map:
                    return row_map[k]
            return default

        return {
            "app_settings": _get_section(SECTION_KEYS["appSettings"], {}),
            "general_settings": _get_section(SECTION_KEYS["generalSettings"], {}),
            "policy_settings": _get_section(SECTION_KEYS["policySettings"], {}),
            "payment_settings": _get_section(SECTION_KEYS["paymentSettings"], {}),
            "contact_us": _get_section(SECTION_KEYS["contactUs"], {}),
            "admin_commission": _get_section(SECTION_KEYS["adminCommission"], {}),
            "status_options": _get_section(SECTION_KEYS["statusOptions"], []),
            "constants": _get_section(SECTION_KEYS["constants"], {}),
            "language_settings": languages,
            "languages": languages,
        }

    async def update_settings(
        self,
        payload: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        app_rows: list[AppSettingDomain] = []

        # 1. Update app_settings sections
        for section_field, aliases in SECTION_KEYS.items():
            val = payload.get(section_field)
            if val is not None:
                # Upsert primary DB key
                primary_key = aliases[0]
                setting = await self.app_settings_repo.upsert_setting(
                    setting_id=primary_key,
                    data=val,
                )
                app_rows.append(setting)

        # 2. Update languages
        lang_settings = payload.get("language_settings") or payload.get("languageSettings")
        lang_rows: list[LanguageDomain] = []
        if lang_settings:
            for lang in lang_settings:
                # lang can be LanguageSettingItem or dict
                l_id = lang.id if hasattr(lang, "id") else lang.get("id")
                l_code = lang.code if hasattr(lang, "code") else lang.get("code")
                l_name = lang.name if hasattr(lang, "name") else lang.get("name")
                l_active = lang.active if hasattr(lang, "active") else lang.get("active", True)
                if l_code and l_name:
                    saved_lang = await self.language_repo.upsert_language(
                        id=l_id,
                        code=l_code,
                        name=l_name,
                        active=l_active,
                    )
                    lang_rows.append(saved_lang)

        # 3. Delete languages
        del_ids = payload.get("language_deleted_ids") or payload.get("languageDeletedIds")
        if del_ids:
            await self.language_repo.delete_languages(del_ids)

        await self.audit_service.log_action(
            action="settings.update",
            resource_type="app_settings",
            resource_id="multi_section",
            summary=f"Updated settings sections: {list(payload.keys())}",
            metadata={"sections": list(payload.keys())},
            ctx=ctx,
        )

        return {
            "app_rows": app_rows,
            "language_rows": lang_rows,
        }

    async def bulk_mutate_languages(
        self,
        upserts: list[Any] | None,
        inserts: list[Any] | None,
        delete_ids: list[UUID] | None,
        ctx: AdminContext | None = None,
    ) -> None:
        items = (upserts or []) + (inserts or [])
        for lang in items:
            l_id = lang.id if hasattr(lang, "id") else lang.get("id")
            l_code = lang.code if hasattr(lang, "code") else lang.get("code")
            l_name = lang.name if hasattr(lang, "name") else lang.get("name")
            l_active = lang.active if hasattr(lang, "active") else lang.get("active", True)
            if l_code and l_name:
                await self.language_repo.upsert_language(
                    id=l_id, code=l_code, name=l_name, active=l_active
                )

        if delete_ids:
            await self.language_repo.delete_languages(delete_ids)

        await self.audit_service.log_action(
            action="languages.bulk_mutate",
            resource_type="languages",
            resource_id="languages_bulk",
            summary=f"Bulk mutate languages: {len(items)} updated, {len(delete_ids or [])} deleted",
            ctx=ctx,
        )

    # --- Mobile App Config ---

    async def list_mobile_app_configs(self) -> list[MobileAppConfigDomain]:
        return await self.mobile_config_repo.list_configs()

    async def update_mobile_app_config(
        self,
        app_key: str,
        updates: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> MobileAppConfigDomain:
        cfg = await self.mobile_config_repo.update_config(app_key=app_key, updates=updates)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mobile app config for '{app_key}' not found",
            )
        await self.audit_service.log_action(
            action="mobile_app_config.update",
            resource_type="mobile_app_config",
            resource_id=app_key,
            summary=f"Updated mobile app config for '{app_key}'",
            metadata=updates,
            ctx=ctx,
        )
        return cfg

    # --- Nav Action Counts ---

    async def get_nav_action_counts(self) -> NavActionCountsDomain:
        return await self.nav_action_counts_repo.get_aggregated_counts()

    # --- Coupons ---

    async def list_coupons(self) -> list[CouponDomain]:
        return await self.coupon_repo.list_coupons()

    async def get_coupon(self, coupon_id: int) -> CouponDomain:
        c = await self.coupon_repo.get_coupon_by_id(coupon_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon {coupon_id} not found",
            )
        return c

    async def create_coupon(
        self,
        data: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> CouponDomain:
        existing = await self.coupon_repo.get_by_code(data["code"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Coupon with code '{data['code']}' already exists",
            )
        coupon = await self.coupon_repo.create_coupon(data)
        await self.audit_service.log_action(
            action="coupon.create",
            resource_type="coupon",
            resource_id=str(coupon.id),
            summary=f"Created coupon '{coupon.code}' ({coupon.amount})",
            ctx=ctx,
        )
        return coupon

    async def update_coupon(
        self,
        coupon_id: int,
        updates: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> CouponDomain:
        await self.get_coupon(coupon_id)
        updated = await self.coupon_repo.update_coupon(coupon_id, updates)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon {coupon_id} not found",
            )
        await self.audit_service.log_action(
            action="coupon.update",
            resource_type="coupon",
            resource_id=str(coupon_id),
            summary=f"Updated coupon {coupon_id}",
            metadata=updates,
            ctx=ctx,
        )
        return updated

    async def delete_coupon(
        self,
        coupon_id: int,
        ctx: AdminContext | None = None,
    ) -> None:
        await self.get_coupon(coupon_id)
        await self.coupon_repo.delete_coupon(coupon_id)
        await self.audit_service.log_action(
            action="coupon.delete",
            resource_type="coupon",
            resource_id=str(coupon_id),
            summary=f"Deleted coupon {coupon_id}",
            ctx=ctx,
        )

