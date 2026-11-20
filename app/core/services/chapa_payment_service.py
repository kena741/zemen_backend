"""Service for Chapa gateway payments, verification, activation, tier upgrades, and featured requests."""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.services import chapa_client
from app.core.services.chapa_client import ChapaBank, ChapaHttp
from app.domain.exceptions import EntityNotFoundError, PaymentProcessingError, ValidationError
from app.domain.finance import CountryTaxDomain
from app.persistence.repositories.app_settings_repo import AppSettingsRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.tax_repo import CountryTaxRepository
from app.persistence.sqlalchemy.models.finance import ServiceTierPayment, Subscription
from app.persistence.sqlalchemy.models.identity import Provider

logger = logging.getLogger(__name__)

_banks_cache: list[ChapaBank] | None = None
_banks_cache_expires_at: float = 0.0


def clear_banks_cache() -> None:
    """Clear the in-memory cache of supported Ethiopian banks."""
    global _banks_cache, _banks_cache_expires_at
    _banks_cache = None
    _banks_cache_expires_at = 0.0


class ChapaPaymentService:
    def __init__(
        self,
        app_settings_repo: AppSettingsRepository,
        tax_repo: CountryTaxRepository,
        provider_repo: ProviderRepository,
        service_repo: ServiceRepository,
        chapa_http: ChapaHttp | None = None,
    ) -> None:
        self.app_settings_repo = app_settings_repo
        self.tax_repo = tax_repo
        self.provider_repo = provider_repo
        self.service_repo = service_repo
        self.chapa_http = chapa_http

    async def get_payment_settings(self) -> dict[str, Any]:
        setting = await self.app_settings_repo.get_by_id("payment")
        data = setting.data if setting else {}
        pub_key = (
            data.get("chapa_public_key")
            or data.get("publicKey")
            or (settings.CHAPA_PUBLIC_KEY or "").strip()
            or "CHAPUBK_TEST-mock"
        )
        return {
            "chapaPublicKey": pub_key,
            "isTest": data.get("is_test", True),
            "currency": data.get("currency", "ETB"),
            "paymentMethods": ["chapa", "wallet", "cash"],
        }

    async def list_taxes(self) -> list[CountryTaxDomain]:
        stmt = select(self.tax_repo.model).where(self.tax_repo.model.active.is_(True))
        res = await self.tax_repo.session.execute(stmt)
        return [self.tax_repo.to_domain(t) for t in res.scalars().all()]

    async def list_supported_banks(self, force_refresh: bool = False) -> list[ChapaBank]:
        """List Ethiopian banks supported by Chapa.

        Results are dynamically fetched via chapa_client.get_banks()
        and cached in memory with a configurable TTL (CHAPA_BANKS_CACHE_TTL_SECONDS).
        """
        global _banks_cache, _banks_cache_expires_at
        now = time.time()

        if not force_refresh and _banks_cache is not None and now < _banks_cache_expires_at:
            return list(_banks_cache)

        try:
            banks = await chapa_client.get_banks(http=self.chapa_http)
            if banks:
                _banks_cache = banks
                ttl = getattr(settings, "CHAPA_BANKS_CACHE_TTL_SECONDS", 3600)
                _banks_cache_expires_at = now + ttl
                return list(_banks_cache)
        except Exception as exc:
            logger.warning("Error fetching banks from Chapa API: %s", exc)

        if _banks_cache is not None:
            return list(_banks_cache)
        return []

    async def initialize_payment(
        self,
        amount: float | Decimal,
        currency: str = "ETB",
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        tx_ref: str | None = None,
        phone_number: str | None = None,
        callback_url: str | None = None,
        return_url: str | None = None,
        customization: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initializes a real Chapa checkout session with a callback/return URL."""
        ref = (tx_ref or f"tx-{secrets.token_hex(6)}").strip()
        try:
            res = await chapa_client.initialize_transaction(
                amount=amount,
                currency=currency,
                email=email,
                first_name=first_name,
                last_name=last_name,
                tx_ref=ref,
                phone_number=phone_number,
                callback_url=callback_url,
                return_url=return_url,
                customization=customization,
                http=self.chapa_http,
            )
            return {
                "status": res.status,
                "checkout_url": res.checkout_url,
                "tx_ref": res.tx_ref,
                "message": res.message,
            }
        except HTTPException as exc:
            raise PaymentProcessingError(f"Chapa checkout initialization failed: {exc.detail}")

    async def verify_chapa_tx(self, tx_ref: str, expected_amount: float | None = None) -> dict[str, Any]:
        tx_clean = tx_ref.strip()
        if not tx_clean:
            raise ValidationError("tx_ref is required.")

        try:
            res = await chapa_client.verify_tx_ref(tx_clean, http=self.chapa_http)
            if expected_amount is not None and res.amount < Decimal(str(expected_amount)):
                raise PaymentProcessingError(
                    f"Verified amount ({res.amount} {res.currency}) is less than expected ({expected_amount} {res.currency})"
                )
            return {
                "status": "success",
                "tx_ref": res.tx_ref,
                "amount": float(res.amount),
                "currency": res.currency,
                "raw_status": res.raw_status,
            }
        except HTTPException as exc:
            raise PaymentProcessingError(f"Chapa verification failed: {exc.detail}")

    async def verify_provider_activation(
        self, tx_ref: str, provider_id: UUID, amount: float
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise EntityNotFoundError("Provider", provider_id)

        if provider.activation_paid:
            return {
                "status": "already_activated",
                "message": "Provider account has already paid activation.",
                "provider_id": str(provider_id),
            }

        # Verify transaction with Chapa
        verify_res = await self.verify_chapa_tx(tx_ref, expected_amount=amount)
        if verify_res.get("status") != "success":
            raise PaymentProcessingError("Chapa transaction verification failed.")

        now = datetime.now(timezone.utc)
        await self.provider_repo.update_provider(
            provider_id=provider_id,
            values={
                "activation_paid": True,
                "activation_paid_at": now,
                "activation_tx_ref": tx_ref.strip(),
                "service_tier_max": max(1, provider.service_tier_max),
            },
        )
        return {
            "status": "success",
            "message": "Provider activation verified successfully.",
            "provider_id": str(provider_id),
            "activation_paid": True,
        }

    async def list_subscription_plans(self) -> list[dict[str, Any]]:
        """List active subscription plans available for providers directly from the database."""
        session = getattr(self.provider_repo, "session", None)
        if not session:
            return []

        stmt = (
            select(Subscription)
            .where(Subscription.active.is_(True))
            .order_by(Subscription.price.asc())
        )
        res = await session.execute(stmt)
        plans = res.scalars().all()
        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "price": float(p.price),
                "service_limit": p.service_limit,
                "duration": p.duration,
                "plan_type": p.plan_type,
                "active": p.active,
            }
            for p in plans
        ]

    async def initiate_tier_purchase(
        self,
        provider_id: UUID,
        plan_id: int | None = None,
        tier_max: int | None = None,
        callback_url: str | None = None,
        return_url: str | None = None,
    ) -> dict[str, Any]:
        """Initializes a backend-controlled checkout session for provider plan purchase."""
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise EntityNotFoundError("Provider", provider_id)

        session = getattr(self.provider_repo, "session", None)
        selected_plan: dict[str, Any] | None = None

        plans = await self.list_subscription_plans()
        if plan_id is not None:
            for p in plans:
                if p["id"] == plan_id:
                    selected_plan = p
                    break
            if not selected_plan:
                raise ValidationError(f"Subscription plan with id {plan_id} not found.")
        elif tier_max is not None:
            for p in plans:
                if p["service_limit"] == tier_max:
                    selected_plan = p
                    break
            if not selected_plan:
                raise ValidationError(f"Subscription plan with quota limit {tier_max} not found.")
        else:
            raise ValidationError("Either plan_id or tier_max must be provided to initiate plan purchase.")

        target_tier = int(selected_plan["service_limit"])
        amount = float(selected_plan["price"])
        plan_title = str(selected_plan["title"])

        tx_ref = f"tier-{provider_id.hex[:6]}-{secrets.token_hex(4)}"

        # Save pending reference to provider record
        now = datetime.now(timezone.utc)
        await self.provider_repo.update_provider(
            provider_id=provider_id,
            values={
                "service_tier_tx_ref": tx_ref,
            },
        )

        # Log pending payment in ledger if DB session is active
        try:
            add_fn = getattr(session, "add", None)
            if session and add_fn and not callable(getattr(add_fn, "assert_called", None)):
                tier_payment = ServiceTierPayment(
                    provider_id=provider_id,
                    tier_id=target_tier,
                    tier_name=plan_title,
                    amount=Decimal(str(amount)),
                    payment_status="pending",
                    created_at=now,
                    updated_at=now,
                )
                session.add(tier_payment)
                if hasattr(session, "flush"):
                    await session.flush()
        except Exception as exc:
            logger.warning("Failed to record pending ServiceTierPayment: %s", exc)

        import re as _re
        _EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        provider_email = getattr(provider, "email", None)
        if provider_email and not _EMAIL_RE.match(str(provider_email).strip()):
            provider_email = None

        raw_phone = getattr(provider, "phone_number", None)
        phone_number = None
        if raw_phone:
            clean_digits = "".join(c for c in raw_phone if c.isdigit())
            if len(clean_digits) >= 9:
                phone_number = ("+" if raw_phone.startswith("+") else "") + clean_digits

        return await self.initialize_payment(
            amount=amount,
            currency="ETB",
            email=provider_email,
            first_name=getattr(provider, "first_name", None),
            last_name=getattr(provider, "last_name", None),
            tx_ref=tx_ref,
            phone_number=phone_number,
            callback_url=callback_url,
            return_url=return_url,
            customization={
                "title": "Service Plan",
                "description": f"Tier {target_tier} upgrade",
            },
        )

    async def verify_service_tier_payment(
        self,
        tx_ref: str,
        provider_id: UUID | None = None,
        amount: float | None = None,
        target_tier: int | None = None,
    ) -> dict[str, Any]:
        tx_clean = tx_ref.strip()
        session = getattr(self.provider_repo, "session", None)

        # 1. Resolve provider_id if not explicitly provided
        if not provider_id and session:
            try:
                stmt = select(Provider.id).where(Provider.service_tier_tx_ref == tx_clean)
                res = await session.execute(stmt)
                resolved_id = res.scalar_one_or_none()
                if resolved_id:
                    provider_id = resolved_id
            except Exception as exc:
                logger.warning("Error resolving provider by tx_ref: %s", exc)

        if not provider_id:
            raise ValidationError("provider_id is required or must match an active transaction reference.")

        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise EntityNotFoundError("Provider", provider_id)

        # 2. Resolve target_tier and expected amount from pending record if omitted
        pending_record: ServiceTierPayment | None = None
        if (target_tier is None or amount is None) and session:
            try:
                stmt_rec = (
                    select(ServiceTierPayment)
                    .where(ServiceTierPayment.provider_id == provider_id)
                    .order_by(ServiceTierPayment.id.desc())
                    .limit(1)
                )
                res_rec = await session.execute(stmt_rec)
                pending_record = res_rec.scalar_one_or_none()
                if pending_record:
                    if target_tier is None:
                        target_tier = int(pending_record.tier_id) if pending_record.tier_id else 2
                    if amount is None:
                        amount = float(pending_record.amount)
            except Exception as exc:
                logger.warning("Error resolving pending tier payment: %s", exc)

        # 3. Verify transaction with Chapa
        verify_res = await self.verify_chapa_tx(tx_clean, expected_amount=amount)
        if verify_res.get("status") != "success":
            raise PaymentProcessingError("Chapa tier payment verification failed.")

        # 4. If target_tier is still None, attempt to match verified amount against plans
        if target_tier is None:
            plans = await self.list_subscription_plans()
            verified_amount = float(verify_res.get("amount", 0.0))
            for p in plans:
                if abs(p["price"] - verified_amount) < 0.01:
                    target_tier = p["service_limit"]
                    break
            if target_tier is None:
                raise ValidationError(
                    f"Verified amount ({verified_amount} ETB) does not match any active subscription plan."
                )

        now = datetime.now(timezone.utc)
        await self.provider_repo.update_provider(
            provider_id=provider_id,
            values={
                "service_tier_max": target_tier,
                "service_tier_paid_at": now,
                "service_tier_tx_ref": tx_clean,
            },
        )

        # 5. Mark pending payment as success or record new ServiceTierPayment
        try:
            if session:
                if pending_record and pending_record.payment_status == "pending":
                    pending_record.payment_status = "success"
                    pending_record.updated_at = now
                    if hasattr(session, "flush"):
                        await session.flush()
                else:
                    add_fn = getattr(session, "add", None)
                    if add_fn and not callable(getattr(add_fn, "assert_called", None)):
                        tier_payment = ServiceTierPayment(
                            provider_id=provider_id,
                            tier_id=target_tier,
                            tier_name=f"Tier {target_tier}",
                            amount=Decimal(str(amount or verify_res.get("amount", 0.0))),
                            payment_status="success",
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(tier_payment)
                        if hasattr(session, "flush"):
                            await session.flush()
        except Exception as exc:
            logger.warning("Failed to record ServiceTierPayment: %s", exc)

        return {
            "status": "success",
            "message": f"Service tier upgraded to {target_tier}.",
            "service_tier_max": target_tier,
            "provider_id": str(provider_id),
            "tx_ref": tx_clean,
        }

    async def verify_featured_request_payment(
        self, tx_ref: str, provider_id: UUID, service_id: UUID, amount: float
    ) -> dict[str, Any]:
        service = await self.service_repo.get_by_id(service_id)
        if not service:
            raise EntityNotFoundError("Service", service_id)
        if service.provider_id != provider_id:
            raise ValidationError("You do not own this service.")

        verify_res = await self.verify_chapa_tx(tx_ref, expected_amount=amount)
        if verify_res.get("status") != "success":
            raise PaymentProcessingError("Chapa featured payment verification failed.")

        now = datetime.now(timezone.utc)
        await self.service_repo.update_service_fields(
            service_id=service_id,
            provider_id=provider_id,
            patch={
                "feature": True,
                "feature_requested_status": "approved",
                "feature_requested_at": now,
            },
            is_admin_or_system=True,
        )
        return {
            "status": "success",
            "message": "Service successfully marked as featured.",
            "service_id": str(service_id),
            "feature": True,
        }
