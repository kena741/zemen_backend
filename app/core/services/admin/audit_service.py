"""Service for recording auditable admin actions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.security.admin_deps import AdminContext
from app.domain.audit import ActivityLogDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository


class AdminAuditService:
    """Orchestrates activity log recording with contextual admin info."""

    def __init__(self, repo: ActivityLogRepository) -> None:
        self.repo = repo

    async def log_action(
        self,
        action: str,
        resource_type: str,
        summary: str,
        ctx: AdminContext | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        env: str = "prod",
    ) -> ActivityLogDomain:
        """Record an admin operation to the audit log."""
        admin_id = ctx.admin_id if ctx else None
        admin_email = ctx.email if ctx else None
        admin_name = ctx.full_name if ctx else None
        admin_role = ctx.role if ctx else None
        route = ctx.route if ctx else None

        return await self.repo.log_activity(
            action=action,
            resource_type=resource_type,
            summary=summary,
            admin_id=admin_id,
            admin_email=admin_email,
            admin_name=admin_name,
            admin_role=admin_role,
            resource_id=resource_id,
            route=route,
            metadata=metadata or {},
            env=env,
        )

    async def list_logs(
        self,
        admin_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActivityLogDomain], int]:
        """Query audit trail with filters."""
        return await self.repo.list_logs(
            admin_id=admin_id,
            action=action,
            resource_type=resource_type,
            offset=offset,
            limit=limit,
        )
