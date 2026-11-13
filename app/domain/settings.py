"""Domain models for App Settings, Languages, Mobile App Config, Coupons, and Nav Action Counts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4


@dataclass
class AppSettingDomain:
    id: str
    data: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass
class LanguageDomain:
    id: UUID
    code: str | None
    name: str | None
    active: bool = True


@dataclass
class MobileAppConfigDomain:
    app_key: str
    maintenance_mode: bool = False
    maintenance_message: str | None = None
    maintenance_affected_versions: list[dict[str, Any]] | dict[str, Any] = field(default_factory=list)
    update_needed: bool = False
    update_message: str | None = None
    update_affected_versions: list[dict[str, Any]] | dict[str, Any] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CouponDomain:
    id: int
    title: str | None
    code: str | None
    amount: Decimal | None = None
    min_amount: Decimal | None = None
    active: bool = True
    is_private: bool = False
    is_fix: bool = True
    expired_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NavActionCountsDomain:
    payout_requests: int = 0
    verify_documents: int = 0
    approve_services: int = 0
    bookings: int = 0
    job_requests: int = 0

    @property
    def total(self) -> int:
        return (
            self.payout_requests
            + self.verify_documents
            + self.approve_services
            + self.bookings
            + self.job_requests
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "/admin/finance/payout-request": self.payout_requests,
            "/admin/verify-documents": self.verify_documents,
            "/admin/services/approve": self.approve_services,
            "/admin/bookings": self.bookings,
            "/admin/customers/job-requests": self.job_requests,
        }

