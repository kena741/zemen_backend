"""Integration tests for Mobile Reviews, Media Storage, and Config APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.v1.routers.reviews import get_review_service
from app.config import settings
from app.core.security.deps import AuthContext
from app.domain.review import ReviewCustomerDomain


@pytest.fixture
def mock_review_service():
    return AsyncMock()


def test_reviews_endpoints(api_client, mock_review_service):
    user_id = uuid4()
    cust_id = uuid4()
    serv_id = uuid4()
    book_id = uuid4()
    rev_id = uuid4()
    now = datetime.now(timezone.utc)

    client = api_client(
        auth_context=AuthContext(user_id=user_id, email="test@zemen.com", roles=["customer"], customer_id=cust_id)
    )
    client.app.dependency_overrides[get_review_service] = lambda: mock_review_service

    rev_domain = ReviewCustomerDomain(
        id=rev_id,
        comment="Outstanding service!",
        rating=4.8,
        customer_id=cust_id,
        service_id=serv_id,
        booking_id=book_id,
        date=now,
        customer_name="Abebe Bikila",
        customer_image=None,
    )

    # 1. Create review
    mock_review_service.add_review.return_value = rev_domain
    res_create = client.post(
        "/api/v1/reviews",
        json={
            "serviceId": str(serv_id),
            "bookingId": str(book_id),
            "rating": 4.8,
            "comment": "Outstanding service!",
        },
    )
    assert res_create.status_code == 201
    assert res_create.json()["id"] == str(rev_id)
    assert res_create.json()["rating"] == 4.8
    assert res_create.json()["comment"] == "Outstanding service!"
    assert res_create.json()["customerName"] == "Abebe Bikila"

    # 2. List reviews for service
    mock_review_service.list_service_reviews.return_value = [rev_domain]
    res_list = client.get(f"/api/v1/reviews?serviceId={serv_id}")
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 1
    assert res_list.json()["items"][0]["id"] == str(rev_id)

    # 3. Get review by booking
    mock_review_service.get_by_booking_id.return_value = rev_domain
    res_by_booking = client.get(f"/api/v1/reviews/by-booking/{book_id}")
    assert res_by_booking.status_code == 200
    assert res_by_booking.json()["bookingId"] == str(book_id)


def test_storage_upload_endpoint(api_client):
    from app.api.v1.routers.storage import get_storage_service

    client = api_client()
    mock_storage = AsyncMock()
    mock_storage.upload_bytes_async.return_value = (
        "https://storage.googleapis.com/betegnabucket/service_proofs/test_proof.png"
    )
    mock_storage.delete_by_public_url_async.return_value = True
    mock_storage.delete_file_async.return_value = True

    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage

    file_bytes = b"fake-image-binary-data"
    files = {"file": ("test_proof.png", BytesIO(file_bytes), "image/png")}

    # 1. Single upload via /storage/upload
    response = client.post("/api/v1/storage/upload?folder=service_proofs", files=files)
    assert response.status_code == 201
    data = response.json()
    assert "https://storage.googleapis.com/betegnabucket/service_proofs/" in data["url"]
    assert data["filename"].endswith(".png")
    assert data["size"] == len(file_bytes)
    assert data["contentType"] == "image/png"
    assert data["bucket"] == settings.GCS_DEFAULT_BUCKET

    # 2. Batch upload via /storage/upload-batch
    files_batch = [
        ("files", ("img1.png", BytesIO(b"data1"), "image/png")),
        ("files", ("img2.png", BytesIO(b"data2"), "image/png")),
    ]
    res_batch = client.post("/api/v1/storage/upload-batch?folder=services", files=files_batch)
    assert res_batch.status_code == 201
    assert len(res_batch.json()["urls"]) == 2
    assert len(res_batch.json()["files"]) == 2

    # 3. Delete by url
    res_del_url = client.delete(
        "/api/v1/storage/delete?url=https://storage.googleapis.com/betegnabucket/service_proofs/test_proof.png"
    )
    assert res_del_url.status_code == 200
    assert res_del_url.json()["deleted"] is True

    # 4. Media alias endpoint
    files_media = {"file": ("avatar.png", BytesIO(b"avatar-data"), "image/png")}
    res_media = client.post("/api/v1/media/upload?folder=users", files=files_media)
    assert res_media.status_code == 201
    assert res_media.json()["bucket"] == settings.GCS_DEFAULT_BUCKET


def test_config_endpoints(api_client):
    client = api_client()

    with patch("app.core.services.config_service.list_banners", new_callable=AsyncMock) as mock_banners, \
         patch("app.core.services.config_service.list_taxes", new_callable=AsyncMock) as mock_taxes, \
         patch("app.core.services.config_service.list_currencies", new_callable=AsyncMock) as mock_currencies, \
         patch("app.core.services.config_service.get_app_setting", new_callable=AsyncMock) as mock_setting, \
         patch("app.core.services.config_service.get_mobile_config", new_callable=AsyncMock) as mock_mconfig:

        # Mock banners
        class DummyBanner:
            id = 1
            image = "https://img.com/banner.png"
            active = True
            service_id = None
            category_id = None
            title = "Promo"
            created_at = datetime.now(timezone.utc)
            updated_at = datetime.now(timezone.utc)

        mock_banners.return_value = [DummyBanner()]
        res_ban = client.get("/api/v1/config/banners")
        assert res_ban.status_code == 200
        assert len(res_ban.json()) == 1

        # Mock app setting
        mock_setting.return_value = {
            "id": "constant",
            "data": {"appName": "Zemen Services", "radius": 50},
            "updated_at": datetime.now(timezone.utc),
        }
        res_set = client.get("/api/v1/config/settings/constant")
        assert res_set.status_code == 200
        assert res_set.json()["id"] == "constant"
        assert res_set.json()["data"]["appName"] == "Zemen Services"

        # Mock mobile config
        class DummyMConfig:
            app_key = "customer_android"
            maintenance_mode = False
            maintenance_message = None
            maintenance_affected_versions = []
            update_needed = False
            update_message = None
            update_affected_versions = []

        mock_mconfig.return_value = DummyMConfig()
        res_cfg = client.get("/api/v1/config/mobile/customer_android")
        assert res_cfg.status_code == 200
        assert res_cfg.json()["app_key"] == "customer_android"
        assert res_cfg.json()["maintenance_mode"] is False

