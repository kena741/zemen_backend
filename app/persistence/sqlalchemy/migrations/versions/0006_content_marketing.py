"""Blog posts, comments, banners, page views, and marketing tracker spreadsheet.

Revision ID: 0006_content_marketing
Revises: 0005_finance_payouts
Create Date: 2026-11-12 13:20:25.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_content_marketing"
down_revision: Union[str, Sequence[str], None] = "0005_finance_payouts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. blog_post
    op.create_table(
        "blog_post",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("cover_image", sa.Text(), nullable=True),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.BigInteger(), nullable=False),
        sa.Column("like_count", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # 2. blog_comment
    op.create_table(
        "blog_comment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_blog_comment_post_id"), "blog_comment", ["post_id"], unique=False)

    # 3. blog_like
    op.create_table(
        "blog_like",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_blog_like_post_id"), "blog_like", ["post_id"], unique=False)

    # 4. marketing_tracker_sheet
    op.create_table(
        "marketing_tracker_sheet",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. marketing_tracker_column
    op.create_table(
        "marketing_tracker_column",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("column_type", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. marketing_tracker_row
    op.create_table(
        "marketing_tracker_row",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketing_tracker_row_sheet_id"), "marketing_tracker_row", ["sheet_id"], unique=False)

    # 7. page_views
    op.create_table(
        "page_views",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_page_views_provider_id"), "page_views", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_page_views_provider_id"), table_name="page_views")
    op.drop_table("page_views")
    op.drop_index(op.f("ix_marketing_tracker_row_sheet_id"), table_name="marketing_tracker_row")
    op.drop_table("marketing_tracker_row")
    op.drop_table("marketing_tracker_column")
    op.drop_table("marketing_tracker_sheet")
    op.drop_index(op.f("ix_blog_like_post_id"), table_name="blog_like")
    op.drop_table("blog_like")
    op.drop_index(op.f("ix_blog_comment_post_id"), table_name="blog_comment")
    op.drop_table("blog_comment")
    op.drop_table("blog_post")
