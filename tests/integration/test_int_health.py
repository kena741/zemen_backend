"""
Integration tests: Health endpoint.

Tests
-----
- GET /api/v1/health → 200, correct body shape and values
"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "zemen-backend"
    assert "environment" in body


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health must be publicly accessible with no token."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
