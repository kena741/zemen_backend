"""Admin permission grammar shared with lolelink-admin (`src/lib/admin-permissions.ts`).

Both apps read the same `admin_role.permissions` rows, so matching rules and
system-role defaults/denials must stay identical to the TypeScript source.
"""

from __future__ import annotations

from collections.abc import Iterable

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "super_admin": ("*",),
    "operations_admin": (
        "providers:read", "providers:write", "providers:verify",
        "services:read", "services:write",
        "catalog:read", "catalog:write",
        "bookings:read", "bookings:write",
        "customers:read", "customers:write",
        "notifications:read", "notifications:write",
    ),
    "finance_admin": ("finance:read", "finance:write"),
    "support_admin": (
        "customers:read", "customers:write",
        "bookings:read", "bookings:write",
        "contact:read", "contact:write",
        "providers:read", "providers:write", "providers:verify",
        "services:read", "services:write",
        "catalog:read", "catalog:write",
        "notifications:read", "notifications:write",
        "settings:read", "settings:write",
        "finance:read",
    ),
    "viewer": (
        "providers:read", "services:read", "catalog:read",
        "bookings:read", "customers:read", "notifications:read",
        "finance:read", "contact:read", "documents:read", "settings:read",
    ),
}

ROLE_PERMISSION_DENYLIST: dict[str, frozenset[str]] = {
    "viewer": frozenset({"services:write"}),
    "support_admin": frozenset({"documents:read", "documents:write"}),
}


def permission_matches(granted: str, required: str) -> bool:
    if granted == "*":
        return True
    if granted.endswith(":*"):
        prefix = granted[:-2]
        return required == prefix or required.startswith(f"{prefix}:")
    return granted == required


def has_permission(permissions: Iterable[str], required: str) -> bool:
    return any(permission_matches(g, required) for g in permissions)


def apply_role_permission_policy(role_slug: str, permissions: Iterable[str]) -> list[str]:
    denied = ROLE_PERMISSION_DENYLIST.get(role_slug, frozenset())
    if not denied:
        return list(permissions)
    out: list[str] = []
    for p in permissions:
        if p in denied:
            continue
        if p == "*" and role_slug in ("viewer", "support_admin"):
            continue
        out.append(p)
    return out


def resolve_role_permissions(role_slug: str, db_permissions: list[str] | None) -> list[str]:
    from_db = [p for p in (db_permissions or []) if isinstance(p, str) and p]
    if from_db:
        return apply_role_permission_policy(role_slug, from_db)
    return apply_role_permission_policy(role_slug, DEFAULT_ROLE_PERMISSIONS.get(role_slug, ()))
