"""Google Cloud Storage (GCS) router for media uploads and deletions."""

from __future__ import annotations

import os
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema
from app.config import settings
from app.core.storage.gcs import GCSStorageService, storage_service

router = APIRouter(tags=["Storage"])


def get_storage_service() -> GCSStorageService:
    return storage_service


class FileUploadResponse(MobileApiSchema):
    url: str
    filename: str
    size: int | None = None
    content_type: str | None = Field(default=None, serialization_alias="contentType")
    path: str | None = None
    bucket: str | None = None


class BatchUploadResponse(MobileApiSchema):
    urls: list[str]
    files: list[FileUploadResponse]


class DeleteFileResponse(MobileApiSchema):
    deleted: bool
    path: str | None = None


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload media file to Google Cloud Storage (profile photo, verification doc, service proof)",
)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Query("media"),
    bucket: str | None = Query(None),
    service: Annotated[GCSStorageService, Depends(get_storage_service)] = None,
) -> FileUploadResponse:
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    unique_name = f"{uuid4().hex}{ext}"
    dest_path = f"{folder.strip('/')}/{unique_name}"
    target_bucket = bucket or settings.GCS_DEFAULT_BUCKET

    content = await file.read()
    public_url = await service.upload_bytes_async(
        data=content,
        destination_path=dest_path,
        bucket_name=target_bucket,
        content_type=file.content_type,
    )

    return FileUploadResponse(
        url=public_url,
        filename=unique_name,
        size=len(content),
        content_type=file.content_type,
        path=dest_path,
        bucket=target_bucket,
    )


@router.post(
    "/upload-batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch upload media files to Google Cloud Storage (service images)",
)
async def upload_batch(
    files: list[UploadFile] = File(...),
    folder: str = Query("media"),
    bucket: str | None = Query(None),
    service: Annotated[GCSStorageService, Depends(get_storage_service)] = None,
) -> BatchUploadResponse:
    target_bucket = bucket or settings.GCS_DEFAULT_BUCKET
    results: list[FileUploadResponse] = []
    urls: list[str] = []

    for file in files:
        ext = os.path.splitext(file.filename or "")[1] or ".png"
        unique_name = f"{uuid4().hex}{ext}"
        dest_path = f"{folder.strip('/')}/{unique_name}"

        content = await file.read()
        public_url = await service.upload_bytes_async(
            data=content,
            destination_path=dest_path,
            bucket_name=target_bucket,
            content_type=file.content_type,
        )

        item = FileUploadResponse(
            url=public_url,
            filename=unique_name,
            size=len(content),
            content_type=file.content_type,
            path=dest_path,
            bucket=target_bucket,
        )
        results.append(item)
        urls.append(public_url)

    return BatchUploadResponse(urls=urls, files=results)


@router.delete(
    "/delete",
    response_model=DeleteFileResponse,
    summary="Delete media file from Google Cloud Storage by public URL or path",
)
async def delete_file(
    url: str | None = Query(None),
    path: str | None = Query(None),
    bucket: str | None = Query(None),
    service: Annotated[GCSStorageService, Depends(get_storage_service)] = None,
) -> DeleteFileResponse:
    if not url and not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'url' or 'path' must be provided",
        )

    if url:
        deleted = await service.delete_by_public_url_async(url)
        return DeleteFileResponse(deleted=deleted, path=url)

    assert path is not None
    target_bucket = bucket or settings.GCS_DEFAULT_BUCKET
    deleted = await service.delete_file_async(destination_path=path, bucket_name=target_bucket)
    return DeleteFileResponse(deleted=deleted, path=path)
