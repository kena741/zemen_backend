"""admin_activity_log writer shared by every admin mutation.

Inserts in the caller's transaction, so a failed log rolls back the change it
describes (lolelink-admin logs after the fact and can lose entries).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import EnvironmentOptions, settings
from app.core.security.admin_deps import AdminContext
from app.persistence.sqlalchemy.models import AdminActivityLog

_SENSITIVE_KEYS = frozenset(
    {"password", "newpassword", "oldpassword", "token", "secret", "servicerolekey", "apikey"}
)


def _is_sensitive(key: str) -> bool:
    k = key.strip().lower().replace("_", "").replace("-", "")
    return k in _SENSITIVE_KEYS or "password" in k


def sanitize_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key, entry in value.items():
        if _is_sensitive(str(key)):
            out[key] = "[redacted]"
        elif isinstance(entry, dict):
            out[key] = sanitize_metadata(entry)
        else:
            out[key] = entry
    return json.loads(json.dumps(out, default=str))


def _env_label() -> str:
    return "prod" if settings.ENVIRONMENT == EnvironmentOptions.PRODUCTION else "staging"


async def log_admin_activity(
    db: AsyncSession,
    ctx: AdminContext,
    *,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AdminActivityLog(
            admin_id=ctx.admin_id,
            admin_email=ctx.email,
            admin_name=ctx.full_name,
            admin_role=ctx.role,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            route=ctx.route,
            summary=summary,
            metadata_={**sanitize_metadata(metadata or {}), "source": "zemen_backend"},
            env=_env_label(),
        )
    )
    await db.flush()
