from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security.admin_deps import AdminContext, get_admin_context
from app.core.security.admin_permissions import (
    has_permission,
    resolve_role_permissions,
)
from app.core.services.admin_audit import sanitize_metadata


def _ctx(permissions: list[str]) -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email=None,
        full_name=None,
        role="custom",
        permissions=permissions,
    )


def test_wildcards_match_like_lolelink():
    assert has_permission(["*"], "finance:write")
    assert has_permission(["providers:*"], "providers:verify")
    assert not has_permission(["providers:*"], "services:write")
    assert not has_permission(["providers:read"], "providers:verify")


def test_system_role_denylist_applies_to_db_grants():
    assert "services:write" not in resolve_role_permissions("viewer", ["services:write", "*"])
    assert resolve_role_permissions("viewer", ["services:write", "*"]) == []
    support = resolve_role_permissions("support_admin", ["documents:read", "providers:verify"])
    assert support == ["providers:verify"]


def test_empty_db_permissions_fall_back_to_defaults():
    assert resolve_role_permissions("finance_admin", []) == ["finance:read", "finance:write"]
    assert resolve_role_permissions("unknown_role", None) == []


def test_metadata_redacts_secrets():
    out = sanitize_metadata({"token": "x", "nested": {"newPassword": "y", "ok": 1}, "service_role_key": "z"})
    assert out == {"token": "[redacted]", "nested": {"newPassword": "[redacted]", "ok": 1}, "service_role_key": "[redacted]"}


def test_admin_routes_require_bearer():
    client = TestClient(create_app())
    assert client.get("/api/v1/admin/me").status_code == 401
    assert client.post(f"/api/v1/admin/services/{uuid4()}/approve").status_code == 401


def test_permission_gate_rejects_before_touching_db():
    app = create_app()
    app.dependency_overrides[get_admin_context] = lambda: _ctx(["services:read"])
    client = TestClient(app)
    assert client.post(f"/api/v1/admin/services/{uuid4()}/approve").status_code == 403
    assert (
        client.post(f"/api/v1/admin/verify-documents/{uuid4()}/reject", json={"reason": "blurry"}).status_code
        == 403
    )
