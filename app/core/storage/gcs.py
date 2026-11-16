"""Google Cloud Storage (GCS) client and file operations."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import BinaryIO

from google.cloud import storage
from google.oauth2 import service_account

from app.config import settings

_storage_client: storage.Client | None = None


def get_gcs_client() -> storage.Client:
    """Initialize or return cached GCS client."""
    global _storage_client
    if _storage_client is not None:
        return _storage_client

    if settings.GCS_CREDENTIALS_JSON:
        cred_info = json.loads(settings.GCS_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(cred_info)
        _storage_client = storage.Client(
            project=settings.GCS_PROJECT_ID or cred_info.get("project_id"),
            credentials=credentials,
        )
    elif settings.GCS_CREDENTIALS_FILE:
        credentials = service_account.Credentials.from_service_account_file(
            settings.GCS_CREDENTIALS_FILE
        )
        _storage_client = storage.Client(
            project=settings.GCS_PROJECT_ID,
            credentials=credentials,
        )
    else:
        # Default application credentials / environment credentials
        _storage_client = storage.Client(project=settings.GCS_PROJECT_ID)

    return _storage_client


class GCSStorageService:
    """Service wrapper for GCS bucket storage operations."""

    def __init__(self, client: storage.Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> storage.Client:
        if self._client is None:
            self._client = get_gcs_client()
        return self._client

    def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        bucket_name: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload raw bytes to GCS and return the object URI or public URL."""
        b_name = bucket_name or settings.GCS_DEFAULT_BUCKET
        bucket = self.client.bucket(b_name)
        blob = bucket.blob(destination_path)
        blob.upload_from_string(data, content_type=content_type)
        return f"{settings.GCS_PUBLIC_URL_BASE.rstrip('/')}/{b_name}/{destination_path.lstrip('/')}"

    def upload_file_stream(
        self,
        file_obj: BinaryIO,
        destination_path: str,
        bucket_name: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload from a binary stream to GCS and return the public URL."""
        b_name = bucket_name or settings.GCS_DEFAULT_BUCKET
        bucket = self.client.bucket(b_name)
        blob = bucket.blob(destination_path)
        blob.upload_from_file(file_obj, content_type=content_type)
        return f"{settings.GCS_PUBLIC_URL_BASE.rstrip('/')}/{b_name}/{destination_path.lstrip('/')}"

    def generate_signed_url(
        self,
        destination_path: str,
        bucket_name: str | None = None,
        expiration_minutes: int = 60,
        http_method: str = "GET",
    ) -> str:
        """Generate a presigned V4 URL for secure time-limited access."""
        b_name = bucket_name or settings.GCS_DEFAULT_BUCKET
        bucket = self.client.bucket(b_name)
        blob = bucket.blob(destination_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method=http_method,
        )

    def delete_file(self, destination_path: str, bucket_name: str | None = None) -> bool:
        """Delete an object from GCS."""
        b_name = bucket_name or settings.GCS_DEFAULT_BUCKET
        bucket = self.client.bucket(b_name)
        blob = bucket.blob(destination_path)
        if blob.exists():
            blob.delete()
            return True
        return False


    def parse_url(self, url: str) -> tuple[str, str]:
        """Extract (bucket_name, destination_path) from a GCS public URL."""
        clean = url.split("?")[0]
        prefix = f"{settings.GCS_PUBLIC_URL_BASE.rstrip('/')}/"
        if clean.startswith(prefix):
            remainder = clean[len(prefix):]
            parts = remainder.split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return parts[0], ""
        return settings.GCS_DEFAULT_BUCKET, clean.lstrip("/")

    def delete_by_public_url(self, url: str) -> bool:
        """Delete an object given its public URL."""
        bucket_name, dest_path = self.parse_url(url)
        return self.delete_file(destination_path=dest_path, bucket_name=bucket_name)

    async def upload_bytes_async(
        self,
        data: bytes,
        destination_path: str,
        bucket_name: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload raw bytes to GCS asynchronously without blocking the event loop."""
        return await asyncio.to_thread(
            self.upload_bytes,
            data,
            destination_path,
            bucket_name,
            content_type,
        )

    async def upload_file_stream_async(
        self,
        file_obj: BinaryIO,
        destination_path: str,
        bucket_name: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload stream to GCS asynchronously without blocking the event loop."""
        return await asyncio.to_thread(
            self.upload_file_stream,
            file_obj,
            destination_path,
            bucket_name,
            content_type,
        )

    async def delete_file_async(
        self,
        destination_path: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Delete an object from GCS asynchronously."""
        return await asyncio.to_thread(
            self.delete_file,
            destination_path,
            bucket_name,
        )

    async def delete_by_public_url_async(
        self,
        url: str,
    ) -> bool:
        """Delete an object given its public URL asynchronously."""
        return await asyncio.to_thread(
            self.delete_by_public_url,
            url,
        )


storage_service = GCSStorageService()

