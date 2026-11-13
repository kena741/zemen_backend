"""Admin RBAC, activity audit, and document management.

Revision ID: 0002_admin_rbac_documents
Revises: 0001_core_identity
Create Date: 2026-11-12 13:20:05.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_admin_rbac_documents"
down_revision: Union[str, Sequence[str], None] = "0001_core_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. admin_role
    op.create_table(
        "admin_role",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # 2. admin
    op.create_table(
        "admin",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_user_id"), "admin", ["user_id"], unique=False)

    # 3. admin_activity_log
    op.create_table(
        "admin_activity_log",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("admin_email", sa.Text(), nullable=True),
        sa.Column("admin_name", sa.Text(), nullable=True),
        sa.Column("admin_role", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("route", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("env", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. documents (system document templates/types)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. admin_documents (internal operations repository)
    op.create_table(
        "admin_documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. document_deliveries
    op.create_table(
        "document_deliveries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("sent_by", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("delivery_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_deliveries_document_id"), "document_deliveries", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_deliveries_recipient_id"), "document_deliveries", ["recipient_id"], unique=False)

    # 7. sub_category_documents
    op.create_table(
        "sub_category_documents",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("sub_category_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 8. verify_documents (provider verification uploads)
    op.create_table(
        "verify_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("providerId", sa.Uuid(), nullable=True),
        sa.Column("documentId", sa.Uuid(), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("isVerify", sa.Boolean(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejectedReason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_verify_documents_providerId"), "verify_documents", ["providerId"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_verify_documents_providerId"), table_name="verify_documents")
    op.drop_table("verify_documents")
    op.drop_table("sub_category_documents")
    op.drop_index(op.f("ix_document_deliveries_recipient_id"), table_name="document_deliveries")
    op.drop_index(op.f("ix_document_deliveries_document_id"), table_name="document_deliveries")
    op.drop_table("document_deliveries")
    op.drop_table("admin_documents")
    op.drop_table("documents")
    op.drop_table("admin_activity_log")
    op.drop_index(op.f("ix_admin_user_id"), table_name="admin")
    op.drop_table("admin")
    op.drop_table("admin_role")
