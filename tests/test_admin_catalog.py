from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.v1.schemas.admin_catalog import AdminHandymanOut, TaxPatch
from app.core.security.admin_deps import AdminContext, get_admin_context
from app.core.services.admin_catalog import _with_is_fix, apply_patch


def test_apply_patch_skips_null_for_required_and_reports_changes():
    row = SimpleNamespace(service_name="Old", description="d", price=10)
    changes = apply_patch(
        row,
        {"service_name": None, "description": None, "price": 10},
        non_nullable=frozenset({"service_name", "price"}),
    )
    assert row.service_name == "Old"
    assert row.description is None
    assert changes == {"description": {"from": "d", "to": None}}


def test_tax_type_drives_is_fix():
    assert _with_is_fix(TaxPatch(type="fixed").model_dump(exclude_unset=True)) == {"type": "fixed", "is_fix": True}
    assert _with_is_fix({"value": 5}) == {"value": 5}


def test_handyman_out_never_exposes_password():
    assert "password" not in AdminHandymanOut.model_fields


def _client(permissions: list[str]) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_admin_context] = lambda: AdminContext(
        admin_id=uuid4(), user_id=uuid4(), email=None, full_name=None, role="custom", permissions=permissions
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/v1/admin/categories", {"categoryName": "X"}),
        ("delete", f"/api/v1/admin/subcategories/{uuid4()}", None),
        ("post", "/api/v1/admin/coupons", {"code": "A", "amount": 1}),
        ("post", "/api/v1/admin/taxes", {"country": "ET", "name": "VAT", "value": 15}),
        ("post", "/api/v1/admin/handymen", {"providerId": str(uuid4())}),
        ("post", "/api/v1/admin/notifications/read", {}),
        ("post", f"/api/v1/admin/services/{uuid4()}/archive", None),
    ],
)
def test_read_only_admin_cannot_write(method, path, body):
    client = _client(["catalog:read", "finance:read", "providers:read", "notifications:read", "services:read"])
    resp = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert resp.status_code == 403


def test_catalog_writer_cannot_touch_taxes():
    client = _client(["catalog:write"])
    assert client.post("/api/v1/admin/taxes", json={"country": "ET", "name": "VAT", "value": 15}).status_code == 403
