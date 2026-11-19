"""
Integration tests: /api/v1/providers endpoints.

Covers:
  - Profile: GET /me, PATCH /me, PUT /me/fcm-token, DELETE /me
  - Lookups: GET /resolve-id, GET /by-phone, GET /{provider_id}
  - Company: GET /me/company, PUT /me/company
  - Handymen: GET /me/handymen, POST /me/handymen, GET /me/handymen/{id}, PATCH /me/handymen/{id}, DELETE /me/handymen/{id}
  - Documents: GET /me/documents, PUT /me/documents, DELETE /me/documents/{id}
  - Payment Methods: GET /me/payment-methods, PUT /me/payment-methods, DELETE /me/payment-methods/{id}
  - Services: GET /me/services, POST /me/services, GET /me/services/{id}, PATCH /me/services/{id}, DELETE /me/services/{id}
"""

import secrets
from uuid import uuid4

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_provider_profile_401(client: AsyncClient):
    resp = await client.get("/api/v1/providers/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_provider_profile_403_for_customer(customer_client):
    client, _ = customer_client
    resp = await client.get("/api/v1/providers/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_provider_profile_200(provider_client):
    client, prov = provider_client
    resp = await client.get("/api/v1/providers/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(prov.id)
    assert data["firstName"] == prov.first_name
    assert data["lastName"] == prov.last_name


@pytest.mark.asyncio
async def test_update_provider_profile_200(provider_client):
    client, prov = provider_client
    payload = {
        "firstName": "UpdatedProv",
        "lastName": "UpdatedLast",
        "address": "Bole Subcity, House 456",
    }
    resp = await client.patch("/api/v1/providers/me", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["firstName"] == "UpdatedProv"
    assert data["lastName"] == "UpdatedLast"
    assert data["address"] == "Bole Subcity, House 456"


@pytest.mark.asyncio
async def test_update_provider_fcm_token_200(provider_client):
    client, prov = provider_client
    resp = await client.put("/api/v1/providers/me/fcm-token", json={"fcmToken": "prov_token_abc123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(prov.id)


@pytest.mark.asyncio
async def test_archive_provider_profile_200(provider_client):
    client, prov = provider_client
    resp = await client.delete("/api/v1/providers/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(prov.id)


@pytest.mark.asyncio
async def test_resolve_provider_id(provider_client):
    client, prov = provider_client
    resp = await client.get("/api/v1/providers/resolve-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providerId"] == str(prov.id)


@pytest.mark.asyncio
async def test_get_provider_by_id_200(client: AsyncClient, seed_provider):
    prov, _, _, _ = await seed_provider()
    resp = await client.get(f"/api/v1/providers/{prov.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(prov.id)


@pytest.mark.asyncio
async def test_get_provider_by_id_404(client: AsyncClient):
    resp = await client.get(f"/api/v1/providers/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Company details
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_provider_company_empty(provider_client):
    client, _ = provider_client
    resp = await client.get("/api/v1/providers/me/company")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_upsert_provider_company(provider_client):
    client, prov = provider_client
    payload = {
        "companyName": "Alpha Cleaners PLC",
        "companyEmail": "contact@alphacleaners.com",
        "companyPhone": "+251911223344",
        "businessRegistrationNumber": "BR-987654",
    }
    resp = await client.put("/api/v1/providers/me/company", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["companyName"] == "Alpha Cleaners PLC"
    assert data["providerId"] == str(prov.id)

    # Verify retrieval
    get_resp = await client.get("/api/v1/providers/me/company")
    assert get_resp.status_code == 200
    assert get_resp.json()["companyName"] == "Alpha Cleaners PLC"


# ---------------------------------------------------------------------------
# Handymen personnel
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handyman_crud(provider_client):
    client, prov = provider_client

    # 1. List initially empty
    resp = await client.get("/api/v1/providers/me/handymen")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create handyman
    random_phone = f"+2519{secrets.randbelow(90000000) + 10000000}"
    create_payload = {
        "firstName": "John",
        "lastName": "Plumber",
        "phoneNumber": random_phone,
        "email": f"john_{secrets.token_hex(4)}@example.com",
        "handymanType": "staff",
    }
    create_resp = await client.post("/api/v1/providers/me/handymen", json=create_payload)
    assert create_resp.status_code == 201
    hm_data = create_resp.json()
    hm_id = hm_data["id"]
    assert hm_data["firstName"] == "John"
    assert hm_data["providerId"] == str(prov.id)

    # 3. Get single handyman
    get_resp = await client.get(f"/api/v1/providers/me/handymen/{hm_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == hm_id

    # 4. Patch handyman
    patch_resp = await client.patch(
        f"/api/v1/providers/me/handymen/{hm_id}",
        json={"firstName": "Johnny"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["firstName"] == "Johnny"

    # 5. Delete handyman
    del_resp = await client.delete(f"/api/v1/providers/me/handymen/{hm_id}")
    assert del_resp.status_code == 204

    # 6. Verify deleted
    get_del = await client.get(f"/api/v1/providers/me/handymen/{hm_id}")
    assert get_del.status_code == 404


# ---------------------------------------------------------------------------
# Verification Documents
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_documents_empty(provider_client):
    client, _ = provider_client
    resp = await client.get("/api/v1/providers/me/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_submit_and_delete_documents(provider_client):
    client, _ = provider_client
    doc_id = uuid4()
    payload = {
        "providerName": "Test Provider",
        "providerEmail": "provider@test.com",
        "documents": [
            {
                "documentId": str(doc_id),
                "documentImage": "https://example.com/license.jpg",
            }
        ],
    }
    resp = await client.put("/api/v1/providers/me/documents", json=payload)
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["documentImage"] == "https://example.com/license.jpg"

    # Delete document
    del_resp = await client.delete(f"/api/v1/providers/me/documents/{doc_id}")
    assert del_resp.status_code == 204


# ---------------------------------------------------------------------------
# Payment Methods
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_payment_methods_crud(provider_client):
    client, prov = provider_client

    # 1. List initially empty
    resp = await client.get("/api/v1/providers/me/payment-methods")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Upsert bank payment method
    payload = {
        "methodType": "bank",
        "holderName": "Test Provider LLC",
        "bankName": "Commercial Bank of Ethiopia",
        "accountNumber": "1000123456789",
    }
    create_resp = await client.put("/api/v1/providers/me/payment-methods", json=payload)
    assert create_resp.status_code == 200
    pm_data = create_resp.json()
    assert pm_data["holderName"] == "Test Provider LLC"
    pm_id = pm_data["id"]

    # 3. Delete payment method
    del_resp = await client.delete(f"/api/v1/providers/me/payment-methods/{pm_id}")
    assert del_resp.status_code == 204


# ---------------------------------------------------------------------------
# Provider Services Management
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_services_crud(provider_client, seed_category, seed_subcategory):
    client, prov = provider_client
    cat = await seed_category(name="Carpentry")
    subcat = await seed_subcategory(category_id=cat.id, name="Furniture Repair")

    # 1. List initially empty
    resp = await client.get("/api/v1/providers/me/services")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create service
    payload = {
        "serviceName": "Chair Fixing",
        "description": "Fix broken wooden chairs",
        "categoryId": str(cat.id),
        "categoryModel": {"id": str(cat.id), "categoryName": cat.category_name},
        "subCategoryId": str(subcat.id),
        "subCategoryModel": {"id": str(subcat.id), "subCategoryName": subcat.sub_category_name},
        "type": "fixed",
        "serviceLocationMode": "provider_location",
        "price": 250.0,
        "serviceImage": ["https://example.com/chair.jpg"],
    }
    create_resp = await client.post("/api/v1/providers/me/services", json=payload)
    assert create_resp.status_code == 201
    svc_data = create_resp.json()
    svc_id = svc_data["id"]
    assert svc_data["serviceName"] == "Chair Fixing"

    # 3. Get single service
    get_resp = await client.get(f"/api/v1/providers/me/services/{svc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == svc_id

    # 4. Patch service
    patch_resp = await client.patch(
        f"/api/v1/providers/me/services/{svc_id}",
        json={"price": 300.0, "description": "Upgraded fixing service"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["price"] == 300.0

    # 5. Delete service
    del_resp = await client.delete(f"/api/v1/providers/me/services/{svc_id}")
    assert del_resp.status_code == 204

    # 6. Verify service is archived (no longer returned in active list)
    active_services = (await client.get("/api/v1/providers/me/services")).json()
    assert svc_id not in [s["id"] for s in active_services]

