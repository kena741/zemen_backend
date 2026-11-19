"""Integration tests for Handymen and Documents catalog endpoints.

Tests:
  - GET /api/v1/handymen/{handyman_id}
  - GET /api/v1/documents/catalog
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Document, Handyman


@pytest.mark.asyncio
async def test_get_handyman_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/handymen/{id} without Authorization returns 401."""
    random_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/handymen/{random_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_handyman_not_found_404(customer_client):
    """GET /api/v1/handymen/{id} for non-existent handyman returns 404."""
    client, _ = customer_client
    random_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/handymen/{random_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_handyman_success_200(
    customer_client,
    db_session: AsyncSession,
    seed_provider,
):
    """GET /api/v1/handymen/{id} returns handyman details when existing."""
    client, _ = customer_client
    prov, _, _, _ = await seed_provider()

    handyman_id = uuid.uuid4()
    user_id = uuid.uuid4()
    h = Handyman(
        id=handyman_id,
        user_id=user_id,
        provider_id=prov.id,
        first_name="Abebe",
        last_name="Kebede",
        phone_number="+251911002233",
        email="abebe@example.com",
        user_name="abebe_k",
        is_active=True,
        active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h)
    await db_session.flush()

    resp = await client.get(f"/api/v1/handymen/{handyman_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(handyman_id)
    assert data["firstName"] == "Abebe"
    assert data["lastName"] == "Kebede"


@pytest.mark.asyncio
async def test_list_document_catalog_200(
    client: AsyncClient,
    seed_document,
):
    """GET /api/v1/documents/catalog returns active document types publicly."""
    doc = await seed_document(name="Trade License", active=True, description="Official municipal business trade license")

    resp = await client.get("/api/v1/documents/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    matching = [d for d in data if d["id"] == str(doc.id)]
    assert len(matching) == 1
    assert matching[0]["name"] == "Trade License"
    assert matching[0]["description"] == "Official municipal business trade license"
