"""Repository for AdminActivityLog persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.domain.audit import ActivityLogDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import AdminActivityLog


class ActivityLogRepository(BaseRepository[AdminActivityLog, ActivityLogDomain]):
    """SQLAlchemy repository for admin audit logs."""

    model = AdminActivityLog

    def to_domain(self, entity: AdminActivityLog) -> ActivityLogDomain:
        return ActivityLogDomain(
            id=entity.id,
            created_at=entity.created_at,
            admin_id=entity.admin_id,
            admin_email=entity.admin_email,
            admin_name=entity.admin_name,
            admin_role=entity.admin_role,
            action=entity.action,
            resource_type=entity.resource_type,
            resource_id=entity.resource_id,
            route=entity.route,
            summary=entity.summary,
            metadata=dict(entity.metadata_) if entity.metadata_ else {},
            env=entity.env,
        )

    def to_model(self, domain: ActivityLogDomain) -> AdminActivityLog:
        return AdminActivityLog(
            id=domain.id,
            created_at=domain.created_at,
            admin_id=domain.admin_id,
            admin_email=domain.admin_email,
            admin_name=domain.admin_name,
            admin_role=domain.admin_role,
            action=domain.action,
            resource_type=domain.resource_type,
            resource_id=domain.resource_id,
            route=domain.route,
            summary=domain.summary,
            metadata_=domain.metadata,
            env=domain.env,
        )

    async def log_activity(
        self,
        action: str,
        resource_type: str,
        summary: str,
        admin_id: UUID | None = None,
        admin_email: str | None = None,
        admin_name: str | None = None,
        admin_role: str | None = None,
        resource_id: str | None = None,
        route: str | None = None,
        metadata: dict[str, Any] | None = None,
        env: str = "prod",
    ) -> ActivityLogDomain:
        """Create and persist an activity log row."""
        entity = AdminActivityLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            route=route,
            summary=summary,
            admin_id=admin_id,
            admin_email=admin_email,
            admin_name=admin_name,
            admin_role=admin_role,
            metadata_=metadata or {},
            env=env,
        )
        self.session.add(entity)
        await self.session.flush()
        return self.to_domain(entity)

    async def list_logs(
        self,
        admin_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActivityLogDomain], int]:
        """Fetch audit logs with filters and total count."""
        stmt = select(AdminActivityLog)
        count_stmt = select(func.count()).select_from(AdminActivityLog)

        filters = []
        if admin_id is not None:
            filters.append(AdminActivityLog.admin_id == admin_id)
        if action:
            filters.append(AdminActivityLog.action == action)
        if resource_type:
            filters.append(AdminActivityLog.resource_type == resource_type)

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)

        stmt = stmt.order_by(AdminActivityLog.created_at.desc()).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        items = [self.to_domain(e) for e in res.scalars().all()]

        return items, total
