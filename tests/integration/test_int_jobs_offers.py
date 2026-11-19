"""Integration tests for Job Requests and Service Offers endpoints.

Endpoints covered:
  - Jobs:
    - GET    /api/v1/jobs
    - GET    /api/v1/jobs/open
    - GET    /api/v1/jobs/my-bids
    - POST   /api/v1/jobs
    - GET    /api/v1/jobs/{job_id}
    - PATCH  /api/v1/jobs/{job_id}
    - POST   /api/v1/jobs/{job_id}/bid
    - POST   /api/v1/jobs/{job_id}/close
    - DELETE /api/v1/jobs/{job_id}
  - Offers:
    - GET    /api/v1/offers
    - POST   /api/v1/offers
    - GET    /api/v1/offers/{offer_id}
    - POST   /api/v1/offers/{offer_id}/cancel
    - POST   /api/v1/offers/{offer_id}/reject
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


# ===========================================================================
# Jobs Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_list_jobs_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/jobs without auth returns 401."""
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_open_jobs_public_200(client: AsyncClient):
    """GET /api/v1/jobs/open returns open jobs listing."""
    resp = await client.get("/api/v1/jobs/open")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_job_request_full_lifecycle(
    client: AsyncClient,
    seed_customer,
    seed_provider,
    seed_service,
):
    """Customer creates a job request, patches it, provider bids, customer closes and deletes."""
    cust, _, _, c_token = await seed_customer()
    prov, _, _, p_token = await seed_provider()
    c_headers = {"Authorization": f"Bearer {c_token}"}
    p_headers = {"Authorization": f"Bearer {p_token}"}

    svc = await seed_service(provider_id=prov.id, allows_custom_offer=True)

    # 1. Customer creates a job
    create_payload = {
        "title": "Need wall repainting in living room",
        "description": "Approx 30 sqm wall repainting with white emulsion",
        "price": "3500",
        "serviceId": str(svc.id),
        "status": "accepted",
    }
    resp = await client.post("/api/v1/jobs", json=create_payload, headers=c_headers)
    assert resp.status_code == 201
    job_data = resp.json()
    job_id = job_data["id"]
    assert job_data["title"] == "Need wall repainting in living room"
    assert job_data["customerId"] == str(cust.id)

    # 2. Customer lists their jobs
    resp = await client.get("/api/v1/jobs?as=customer", headers=c_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(j["id"] == job_id for j in items)

    # 3. Retrieve by ID
    resp = await client.get(f"/api/v1/jobs/{job_id}", headers=c_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id

    # 4. Patch job
    patch_payload = {"title": "Updated: Need urgent wall repainting", "price": "4000"}
    resp = await client.patch(f"/api/v1/jobs/{job_id}", json=patch_payload, headers=c_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated: Need urgent wall repainting"

    # 5. Provider bids on the job
    bid_payload = {"bidPrice": "3800", "message": "I can do this tomorrow with premium paint!"}
    resp = await client.post(f"/api/v1/jobs/{job_id}/bid", json=bid_payload, headers=p_headers)
    assert resp.status_code == 200
    bidded_job = resp.json()
    assert len(bidded_job["bidList"]) > 0

    # 6. Provider lists my-bids
    resp = await client.get("/api/v1/jobs/my-bids", headers=p_headers)
    assert resp.status_code == 200
    assert any(j["id"] == job_id for j in resp.json())

    # 7. Customer closes the job
    resp = await client.post(f"/api/v1/jobs/{job_id}/close", headers=c_headers)
    assert resp.status_code == 200

    # 8. Customer deletes the job
    resp = await client.delete(f"/api/v1/jobs/{job_id}", headers=c_headers)
    assert resp.status_code == 204


# ===========================================================================
# Service Offers Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_list_offers_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/offers without auth returns 401."""
    resp = await client.get("/api/v1/offers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_offer_customer_cancel_flow(
    client: AsyncClient,
    seed_customer,
    seed_provider,
    seed_service,
):
    """Customer creates an offer and cancels it."""
    cust, _, _, c_token = await seed_customer()
    prov, _, _, _ = await seed_provider()
    c_headers = {"Authorization": f"Bearer {c_token}"}

    svc = await seed_service(provider_id=prov.id, allows_custom_offer=True)

    payload = {
        "serviceId": str(svc.id),
        "providerId": str(prov.id),
        "offeredPrice": 1200.0,
        "message": "Can you do it for 1200 ETB?",
        "serviceDescription": "AC Maintenance discount request",
        "bookingAddress": {"city": "Addis Ababa", "address": "Bole Road, Apt 4B"},
    }

    # 1. Customer creates an offer
    resp = await client.post("/api/v1/offers", json=payload, headers=c_headers)
    assert resp.status_code == 201
    offer_data = resp.json()
    offer_id = offer_data["id"]
    assert offer_data["offeredPrice"] == 1200.0
    assert offer_data["status"] == "pending"

    # 2. Customer lists offers
    resp = await client.get("/api/v1/offers?as=customer", headers=c_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(o["id"] == offer_id for o in items)

    # 3. Retrieve offer by ID
    resp = await client.get(f"/api/v1/offers/{offer_id}", headers=c_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == offer_id

    # 4. Customer cancels the offer
    resp = await client.post(f"/api/v1/offers/{offer_id}/cancel", headers=c_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_offer_provider_reject_flow(
    client: AsyncClient,
    seed_customer,
    seed_provider,
    seed_service,
):
    """Customer creates an offer, provider rejects it."""
    cust, _, _, c_token = await seed_customer()
    prov, _, _, p_token = await seed_provider()
    c_headers = {"Authorization": f"Bearer {c_token}"}
    p_headers = {"Authorization": f"Bearer {p_token}"}

    svc = await seed_service(provider_id=prov.id, allows_custom_offer=True)

    payload = {
        "serviceId": str(svc.id),
        "providerId": str(prov.id),
        "offeredPrice": 800.0,
        "message": "Offering 800 ETB",
        "serviceDescription": "Plumbing leak fix",
        "bookingAddress": {"city": "Addis Ababa", "address": "Sarbet"},
    }

    resp = await client.post("/api/v1/offers", json=payload, headers=c_headers)
    assert resp.status_code == 201
    offer_id = resp.json()["id"]

    # Provider rejects
    resp = await client.post(f"/api/v1/offers/{offer_id}/reject", headers=p_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
