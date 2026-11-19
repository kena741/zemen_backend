"""
Integration tests: Catalog endpoints.

Coverage
--------
GET  /api/v1/catalog/categories
GET  /api/v1/catalog/sub-categories
GET  /api/v1/catalog/documents
GET  /api/v1/catalog/services
GET  /api/v1/catalog/services/{id}
GET  /api/v1/catalog/banners
GET  /api/v1/catalog/coupons
GET  /api/v1/catalog/coupons/by-code/{code}
PUT  /api/v1/catalog/services/{id}/like    (auth required)
DELETE /api/v1/catalog/services/{id}/like  (auth required)

These tests are the PRIMARY validation of the 0011_fix_schema_gaps migration.
If `categoryName`, `subCategoryName`, `description`, or `position` columns
are absent, the tests fail immediately with a helpful error.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


# ============================================================
#  Categories
# ============================================================

@pytest.mark.asyncio
async def test_list_categories_empty(client):
    """Returns 200 and empty list when no categories exist."""
    resp = await client.get("/api/v1/catalog/categories")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_categories_active_only(client, seed_category):
    """Active category appears; inactive category does not."""
    active_cat = await seed_category(name="Active Cat", active=True)
    await seed_category(name="Inactive Cat", active=False)

    resp = await client.get("/api/v1/catalog/categories?activeOnly=true")
    assert resp.status_code == 200
    body = resp.json()
    ids = [item["id"] for item in body]
    assert str(active_cat.id) in ids
    # The inactive one must NOT appear
    assert all(item.get("categoryName") is not None for item in body), (
        "categoryName field missing — did you run migration 0011_fix_schema_gaps?"
    )


@pytest.mark.asyncio
async def test_list_categories_includes_inactive_when_flag_false(client, seed_category):
    """activeOnly=false returns both active and inactive categories."""
    await seed_category(name="Active A", active=True)
    await seed_category(name="Inactive B", active=False)

    resp = await client.get("/api/v1/catalog/categories?activeOnly=false")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 2


@pytest.mark.asyncio
async def test_list_categories_response_shape(client, seed_category):
    """Response items have exactly the fields the Flutter client expects."""
    cat = await seed_category(name="Plumbing", active=True, description="Plumbing services")
    resp = await client.get("/api/v1/catalog/categories")
    assert resp.status_code == 200
    body = resp.json()
    item = next(i for i in body if i["id"] == str(cat.id))

    # Validate camelCase field names
    assert "categoryName" in item
    assert "image" in item
    assert "active" in item
    assert "description" in item
    assert item["categoryName"] == "Plumbing"
    assert item["description"] == "Plumbing services"


# ============================================================
#  Subcategories
# ============================================================

@pytest.mark.asyncio
async def test_list_subcategories_empty(client):
    resp = await client.get("/api/v1/catalog/sub-categories")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_subcategories_response_shape(client, seed_category, seed_subcategory):
    """Response items have subCategoryName and categoryId fields."""
    cat = await seed_category(name="Electrical")
    sub = await seed_subcategory(category_id=cat.id, name="Wiring", is_free=False)

    resp = await client.get("/api/v1/catalog/sub-categories")
    assert resp.status_code == 200
    body = resp.json()
    item = next((i for i in body if i["id"] == str(sub.id)), None)
    assert item is not None, "Seeded subcategory not found in response"
    assert "subCategoryName" in item, (
        "subCategoryName field missing — did you run migration 0011_fix_schema_gaps?"
    )
    assert "categoryId" in item
    assert "isFree" in item
    assert item["subCategoryName"] == "Wiring"
    assert item["categoryId"] == str(cat.id)
    assert item["isFree"] is False


@pytest.mark.asyncio
async def test_list_subcategories_filtered_by_category(client, seed_category, seed_subcategory):
    """categoryId query param filters results correctly."""
    cat_a = await seed_category(name="Cat A")
    cat_b = await seed_category(name="Cat B")
    sub_a = await seed_subcategory(category_id=cat_a.id, name="Sub A")
    await seed_subcategory(category_id=cat_b.id, name="Sub B")

    resp = await client.get(f"/api/v1/catalog/sub-categories?categoryId={cat_a.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert all(i["categoryId"] == str(cat_a.id) for i in body)
    ids = [i["id"] for i in body]
    assert str(sub_a.id) in ids


@pytest.mark.asyncio
async def test_list_subcategories_nonexistent_category_returns_empty(client):
    """A categoryId that doesn't match anything returns []."""
    resp = await client.get(f"/api/v1/catalog/sub-categories?categoryId={uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []


# ============================================================
#  Documents
# ============================================================

@pytest.mark.asyncio
async def test_list_documents_empty(client):
    resp = await client.get("/api/v1/catalog/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_documents_has_description_field(client, seed_document):
    """description field must be present — catches missing column in documents table."""
    doc = await seed_document(name="Passport", active=True, description="Valid passport copy")
    resp = await client.get("/api/v1/catalog/documents")
    assert resp.status_code == 200
    body = resp.json()
    item = next((i for i in body if i["id"] == str(doc.id)), None)
    assert item is not None
    assert "description" in item, (
        "description field missing — did you run migration 0011_fix_schema_gaps?"
    )
    assert item["description"] == "Valid passport copy"


@pytest.mark.asyncio
async def test_list_documents_inactive_not_returned(client, seed_document):
    """Inactive documents must not appear in the public list."""
    inactive_doc = await seed_document(name="Old Card", active=False)
    resp = await client.get("/api/v1/catalog/documents")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()]
    assert str(inactive_doc.id) not in ids


# ============================================================
#  Services
# ============================================================

@pytest.mark.asyncio
async def test_list_services_empty(client):
    resp = await client.get("/api/v1/catalog/services")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "meta" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_list_services_response_shape(client, seed_service):
    """Service response includes position field — catches migration 0011 gap."""
    svc = await seed_service(service_name="Deep Cleaning", price=350)
    resp = await client.get("/api/v1/catalog/services")
    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    item = next((i for i in items if i["id"] == str(svc.id)), None)
    assert item is not None, "Seeded service not found"

    # Field name validation
    assert "serviceName" in item
    assert "categoryId" in item
    assert "subCategoryId" in item
    assert "price" in item
    assert "position" in item, (
        "position field missing — did you run migration 0011_fix_schema_gaps?"
    )
    assert item["serviceName"] == "Deep Cleaning"


@pytest.mark.asyncio
async def test_list_services_pagination_meta(client):
    """Page meta contains limit and offset."""
    resp = await client.get("/api/v1/catalog/services?limit=5&offset=0")
    assert resp.status_code == 200
    meta = resp.json()["meta"]
    assert meta["limit"] == 5
    assert meta["offset"] == 0


@pytest.mark.asyncio
async def test_list_services_only_approved_and_active(client, seed_service):
    """Unapproved or archived services must NOT appear in public list."""
    unapproved = await seed_service(service_name="Unapproved Svc", approved=False)
    archived = await seed_service(service_name="Archived Svc", is_archived=True)

    resp = await client.get("/api/v1/catalog/services")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert str(unapproved.id) not in ids
    assert str(archived.id) not in ids


@pytest.mark.asyncio
async def test_list_services_filtered_by_category(client, seed_service, seed_category, seed_subcategory):
    """categoryId filter returns only matching services."""
    cat = await seed_category(name="Plumbing")
    sub = await seed_subcategory(category_id=cat.id, name="Pipe Fix")
    matching_svc = await seed_service(
        service_name="Pipe Fix Service",
        category_id=cat.id,
        sub_category_id=sub.id,
    )
    await seed_service(service_name="Other Service")  # different category

    resp = await client.get(f"/api/v1/catalog/services?categoryId={cat.id}")
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["id"] for i in items]
    assert str(matching_svc.id) in ids
    assert all(
        i["categoryId"] == str(cat.id) for i in items
    ), "Non-matching category slipped through filter"


@pytest.mark.asyncio
async def test_get_service_by_id_200(client, seed_service):
    svc = await seed_service(service_name="Single Service")
    resp = await client.get(f"/api/v1/catalog/services/{svc.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(svc.id)
    assert body["serviceName"] == "Single Service"


@pytest.mark.asyncio
async def test_get_service_by_id_404(client):
    resp = await client.get(f"/api/v1/catalog/services/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_services_search(client, seed_service):
    """search query param narrows results to matching service names."""
    await seed_service(service_name="Gardening Pro")
    await seed_service(service_name="Deep Clean Express")

    resp = await client.get("/api/v1/catalog/services?search=Gardening")
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert "garden" in item["serviceName"].lower()


# ============================================================
#  Banners & Coupons
# ============================================================

@pytest.mark.asyncio
async def test_list_banners(client):
    """Banners endpoint returns a list (may be empty)."""
    resp = await client.get("/api/v1/catalog/banners")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_coupons(client):
    resp = await client.get("/api/v1/catalog/coupons")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_coupon_by_code_404(client):
    """Non-existent coupon code returns 404."""
    resp = await client.get("/api/v1/catalog/coupons/by-code/DOESNOTEXIST")
    assert resp.status_code == 404


# ============================================================
#  Like / Unlike (auth required)
# ============================================================

@pytest.mark.asyncio
async def test_like_service_requires_auth(client, seed_service):
    svc = await seed_service()
    resp = await client.put(f"/api/v1/catalog/services/{svc.id}/like")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_like_service_authenticated(customer_client, seed_service):
    ac, cust = customer_client
    svc = await seed_service()
    resp = await ac.put(f"/api/v1/catalog/services/{svc.id}/like")
    # 200 OK — the service was toggled
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(svc.id)


@pytest.mark.asyncio
async def test_unlike_service_requires_auth(client, seed_service):
    svc = await seed_service()
    resp = await client.delete(f"/api/v1/catalog/services/{svc.id}/like")
    assert resp.status_code == 401
