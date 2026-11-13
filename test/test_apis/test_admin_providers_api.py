"""Integration tests for Admin Providers and Verification API endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.persistence.sqlalchemy.models.finance import ProviderPaymentMethod
from app.persistence.sqlalchemy.models.identity import Provider
from .conftest import ApiTestDbSession


@pytest.fixture
def super_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.fixture
def limited_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="viewer@lolelink.com",
        full_name="Viewer Admin",
        role="viewer",
        permissions=["catalog:read"],
    )


def test_list_providers_success(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_p = Provider(
        id=uuid4(),
        user_id=uuid4(),
        first_name="Almaz",
        last_name="Ayana",
        email="almaz@example.com",
        phone_number="+251911002233",
        active=True,
        wallet_amount="250.00",
        activation_paid=True,
        service_tier_max=1,
        verified_subcategory_ids=[],
        created_at=now,
        updated_at=now,
    )
    db = ApiTestDbSession(scalars_return=[mock_p])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/providers")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["firstName"] == "Almaz"
    assert data[0]["walletAmount"] == "250.00"


def test_list_providers_forbidden(api_client, limited_admin_context):
    client = api_client(admin_context=limited_admin_context)
    res = client.get("/api/v1/admin/providers")
    assert res.status_code == 403


def test_get_provider_by_id(api_client, super_admin_context):
    prov_id = uuid4()
    now = datetime.now(timezone.utc)
    mock_p = Provider(
        id=prov_id,
        user_id=uuid4(),
        first_name="Haile",
        last_name="Gebrselassie",
        email="haile@example.com",
        phone_number="+251911998877",
        active=True,
        wallet_amount="5000.00",
        activation_paid=True,
        service_tier_max=5,
        verified_subcategory_ids=[],
        created_at=now,
        updated_at=now,
    )
    db = ApiTestDbSession(scalar_return=mock_p)

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get(f"/api/v1/admin/providers/{prov_id}")
    assert res.status_code == 200
    assert res.json()["data"]["id"] == str(prov_id)
    assert res.json()["data"]["firstName"] == "Haile"


def test_get_bank_details(api_client, super_admin_context):
    prov_id = uuid4()
    now = datetime.now(timezone.utc)
    mock_p = Provider(
        id=prov_id,
        user_id=uuid4(),
        first_name="Haile",
        last_name="Gebrselassie",
        active=True,
        verified_subcategory_ids=[],
        created_at=now,
        updated_at=now,
    )
    mock_bank = ProviderPaymentMethod(
        id=uuid4(),
        provider_id=prov_id,
        method_type="bank",
        method_code="cbe",
        method_name="Commercial Bank of Ethiopia",
        holder_name="Haile G",
        account_number="100099887766",
        is_default=True,
        is_active=True,
        currency="ETB",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    db = ApiTestDbSession(scalar_return=mock_p, scalars_return=[mock_bank])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get(f"/api/v1/admin/providers/{prov_id}/bank-details")
    assert res.status_code == 200
    assert res.json()["data"]["accountNumber"] == "100099887766"
    assert len(res.json()["methods"]) == 1


def test_nav_action_counts(api_client, super_admin_context):
    db = ApiTestDbSession(scalar_return=5)
    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/nav-action-counts")
    assert res.status_code == 200
    assert res.json()["counts"]["/admin/verify-documents"] == 5

