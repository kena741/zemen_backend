from fastapi.testclient import TestClient

from app.api import create_app


def test_health():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "zemen-backend"
