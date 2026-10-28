"""Admin review of provider services: approval and featured-listing decisions.

Ports `approveServicesSlice.ts` from lolelink-admin. Featured payments are
verified by the `verify-featured-request-payment` Edge Function; this module
only records the admin's decision.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.admin_deps import AdminContext
from app.core.services.admin_audit import log_admin_activity
from app.persistence.sqlalchemy.models import Service

FeatureDecision = Literal["accept", "reject", "remove"]

_FEATURE_PAYLOAD: dict[FeatureDecision, tuple[bool, str]] = {
    "accept": (True, "accepted"),
    "reject": (False, "rejected"),
    "remove": (False, "none"),
}


async def get_service(db: AsyncSession, service_id: UUID) -> Service | None:
    return (
        await db.execute(select(Service).where(Service.id == service_id).with_for_update())
    ).scalar_one_or_none()


async def approve_service(db: AsyncSession, ctx: AdminContext, service: Service) -> Service:
    was_approved = service.approved
    service.approved = True
    await db.flush()
    await log_admin_activity(
        db,
        ctx,
        action="approve",
        resource_type="service",
        resource_id=service.id,
        summary=f"Approved service {service.id}",
        metadata={"changes": {"approved": {"from": was_approved, "to": True}}},
    )
    await db.refresh(service)
    return service


async def approve_provider_services(
    db: AsyncSession, ctx: AdminContext, provider_id: UUID
) -> list[UUID]:
    ids = list(
        (
            await db.execute(
                update(Service)
                .where(
                    Service.provider_id == provider_id,
                    Service.is_archived.is_not(True),
                    Service.approved.is_not(True),
                )
                .values(approved=True)
                .returning(Service.id)
            )
        ).scalars()
    )
    if ids:
        await log_admin_activity(
            db,
            ctx,
            action="approve",
            resource_type="service",
            resource_id=provider_id,
            summary=f"Approved {len(ids)} service(s) for provider {provider_id}",
            metadata={"service_ids": [str(i) for i in ids]},
        )
    return ids


async def decide_feature(
    db: AsyncSession, ctx: AdminContext, service: Service, decision: FeatureDecision
) -> Service:
    feature, status_value = _FEATURE_PAYLOAD[decision]
    before = {"feature": service.feature, "feature_requested_status": service.feature_requested_status}
    service.feature = feature
    service.feature_requested_status = status_value
    await db.flush()

    action, summary = {
        "accept": ("approve", f"Approved featured listing request for service {service.id}"),
        "reject": ("reject", f"Rejected featured listing request for service {service.id}"),
        "remove": ("update", f"Removed featured status from service {service.id}"),
    }[decision]
    await log_admin_activity(
        db,
        ctx,
        action=action,
        resource_type="service",
        resource_id=service.id,
        summary=summary,
        metadata={
            "changes": {
                "feature": {"from": before["feature"], "to": feature},
                "feature_requested_status": {
                    "from": before["feature_requested_status"],
                    "to": status_value,
                },
            }
        },
    )
    await db.refresh(service)
    return service
