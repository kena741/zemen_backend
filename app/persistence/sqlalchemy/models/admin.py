from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Text, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base


class Admin(Base):
    __tablename__ = "admin"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminRole(Base):
    __tablename__ = "admin_role"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminActivityLog(Base):
    __tablename__ = "admin_activity_log"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    admin_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    admin_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    route: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    env: Mapped[str] = mapped_column(Text, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubCategoryDocument(Base):
    __tablename__ = "sub_category_documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    sub_category_id: Mapped[UUID] = mapped_column("subCategoryId", Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column("documentId", Uuid(as_uuid=True), nullable=False)
    is_required: Mapped[bool | None] = mapped_column("isRequired", Boolean, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class VerifyDocument(Base):
    __tablename__ = "verify_documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)
    provider_id: Mapped[UUID] = mapped_column("providerId", Uuid(as_uuid=True), nullable=False, index=True)
    provider_name: Mapped[str | None] = mapped_column("providerName", Text, nullable=True)
    provider_email: Mapped[str | None] = mapped_column("providerEmail", Text, nullable=True)
    document_id: Mapped[UUID | None] = mapped_column("documentId", Uuid(as_uuid=True), nullable=True)
    document_image: Mapped[str | None] = mapped_column("documentImage", Text, nullable=True)
    is_verify: Mapped[bool | None] = mapped_column("isVerify", Boolean, nullable=True)
