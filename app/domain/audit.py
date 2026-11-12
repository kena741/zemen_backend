"""Internal domain models for Admin Activity Audit Logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ActivityLogDomain:
    """Domain model representing an audited admin operation."""

    id: UUID
    created_at: datetime
    admin_id: UUID | None
    admin_email: str | None
    admin_name: str | None
    admin_role: str | None
    action: str
    resource_type: str
    resource_id: str | None
    route: str | None
    summary: str
    metadata: dict[str, Any]
    env: str
