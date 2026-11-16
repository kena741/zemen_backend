"""Unit tests for GCSStorageService."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from app.config import settings
from app.core.storage.gcs import GCSStorageService


@pytest.fixture
def mock_gcs_client():
    client = MagicMock()
    bucket = MagicMock()
    blob = MagicMock()
    client.bucket.return_value = bucket
    bucket.blob.return_value = blob
    blob.exists.return_value = True
    blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
    return client


@pytest.fixture
def gcs_service(mock_gcs_client):
    return GCSStorageService(client=mock_gcs_client)


def test_gcs_parse_url(gcs_service):
    # Standard public GCS URL
    url = f"{settings.GCS_PUBLIC_URL_BASE}/betegnabucket/media/test.png"
    b_name, path = gcs_service.parse_url(url)
    assert b_name == "betegnabucket"
    assert path == "media/test.png"

    # URL with query params
    url_with_query = f"{settings.GCS_PUBLIC_URL_BASE}/betegnabucket/proofs/doc.pdf?auth=token"
    b_name, path = gcs_service.parse_url(url_with_query)
    assert b_name == "betegnabucket"
    assert path == "proofs/doc.pdf"

    # Fallback path only
    raw_path = "avatars/user123.jpg"
    b_name, path = gcs_service.parse_url(raw_path)
    assert b_name == settings.GCS_DEFAULT_BUCKET
    assert path == "avatars/user123.jpg"


def test_gcs_upload_bytes(gcs_service, mock_gcs_client):
    data = b"image-content-bytes"
    dest_path = "media/pic.png"
    public_url = gcs_service.upload_bytes(
        data=data,
        destination_path=dest_path,
        content_type="image/png",
    )

    mock_gcs_client.bucket.assert_called_with(settings.GCS_DEFAULT_BUCKET)
    mock_gcs_client.bucket().blob.assert_called_with(dest_path)
    mock_gcs_client.bucket().blob().upload_from_string.assert_called_once_with(
        data, content_type="image/png"
    )
    assert public_url == f"{settings.GCS_PUBLIC_URL_BASE}/{settings.GCS_DEFAULT_BUCKET}/{dest_path}"


@pytest.mark.asyncio
async def test_gcs_upload_bytes_async(gcs_service, mock_gcs_client):
    data = b"async-bytes"
    dest_path = "proofs/file.pdf"
    public_url = await gcs_service.upload_bytes_async(
        data=data,
        destination_path=dest_path,
        content_type="application/pdf",
    )

    assert public_url == f"{settings.GCS_PUBLIC_URL_BASE}/{settings.GCS_DEFAULT_BUCKET}/{dest_path}"


def test_gcs_delete_file(gcs_service, mock_gcs_client):
    blob = mock_gcs_client.bucket().blob()

    # Exists = True
    blob.exists.return_value = True
    deleted = gcs_service.delete_file("media/pic.png")
    assert deleted is True
    blob.delete.assert_called_once()

    # Exists = False
    blob.exists.return_value = False
    deleted_false = gcs_service.delete_file("media/missing.png")
    assert deleted_false is False


def test_gcs_delete_by_public_url(gcs_service, mock_gcs_client):
    blob = mock_gcs_client.bucket().blob()
    blob.exists.return_value = True

    url = f"{settings.GCS_PUBLIC_URL_BASE}/betegnabucket/media/pic.png"
    deleted = gcs_service.delete_by_public_url(url)
    assert deleted is True
    mock_gcs_client.bucket.assert_called_with("betegnabucket")
    mock_gcs_client.bucket().blob.assert_called_with("media/pic.png")


def test_gcs_generate_signed_url(gcs_service, mock_gcs_client):
    blob = mock_gcs_client.bucket().blob()
    url = gcs_service.generate_signed_url("media/private.pdf", expiration_minutes=30)
    assert url == "https://storage.googleapis.com/signed-url"
    blob.generate_signed_url.assert_called_once()
