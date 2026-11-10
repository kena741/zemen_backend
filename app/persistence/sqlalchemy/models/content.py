"""Content & marketing models: blog, banners, marketing tracker, page views."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------


class BlogPost(Base):
    """A blog/article post. Status: 'draft' | 'published' | 'archived'."""

    __tablename__ = "blog_post"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # draft | published | archived
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    view_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    like_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class BlogComment(Base):
    """A comment on a blog post. Status: 'pending' | 'approved' | 'hidden'.

    DB constraints (from schema_public.sql):
      - body: 2–2000 chars
      - full_name: 2–80 chars
      - phone: 9–20 chars
    Validation is enforced at the service layer to mirror these CHECK constraints.
    """

    __tablename__ = "blog_comment"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    post_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # approved | pending | hidden
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BlogLike(Base):
    """An anonymous visitor like on a blog post, identified by visitor_key."""

    __tablename__ = "blog_like"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    post_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    visitor_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Marketing tracker (CRM-lite spreadsheet feature)
# ---------------------------------------------------------------------------


class MarketingTrackerSheet(Base):
    """A named sheet (tab) in the marketing tracker."""

    __tablename__ = "marketing_tracker_sheet"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketingTrackerColumn(Base):
    """A column definition within a marketing tracker sheet."""

    __tablename__ = "marketing_tracker_column"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    column_type: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketingTrackerRow(Base):
    """A data row in a marketing tracker sheet.

    `values` is a JSONB blob where keys are column `key` strings and values
    are the cell data for that row. Schema is fully dynamic.
    """

    __tablename__ = "marketing_tracker_row"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    sheet_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Page views
# ---------------------------------------------------------------------------


class PageView(Base):
    """Daily page-view counter per provider profile.

    One row per (provider_id, date_id) pair — upserted on each view.
    """

    __tablename__ = "page_views"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    date_id: Mapped[datetime] = mapped_column(
        # Stored as `date` in Postgres but mapped via DateTime for compat
        DateTime(timezone=False), nullable=False
    )
    count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

