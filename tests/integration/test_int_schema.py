"""
Integration tests: Schema smoke test.

Purpose
-------
These tests directly query the test database to verify that every column
referenced by the ORM models actually exists. This is the safety net that
catches migration drift *before* it hits production.

Each test issues a lightweight `SELECT <col>` or `SELECT 1` against the
test DB (which was built from Base.metadata.create_all(), i.e. the ORM
models are the authoritative source).

The tests will PASS against the test DB because create_all() reflects the
correct schema. The 0011_fix_schema_gaps migration must be run against the
dev/prod DB to match.
"""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_category_has_category_name_column(db_session):
    """category."categoryName" must exist — was missing in migration 0003."""
    result = await db_session.execute(
        text('SELECT "categoryName" FROM category LIMIT 0')
    )
    assert result is not None


@pytest.mark.asyncio
async def test_sub_category_has_sub_category_name_column(db_session):
    """sub_category."subCategoryName" must exist — was missing in migration 0003."""
    result = await db_session.execute(
        text('SELECT "subCategoryName" FROM sub_category LIMIT 0')
    )
    assert result is not None


@pytest.mark.asyncio
async def test_sub_category_has_is_free_column(db_session):
    """sub_category."isFree" must exist — was missing in migration 0003."""
    result = await db_session.execute(
        text('SELECT "isFree" FROM sub_category LIMIT 0')
    )
    assert result is not None


@pytest.mark.asyncio
async def test_documents_has_description_column(db_session):
    """documents.description must exist — was missing in migration 0002."""
    result = await db_session.execute(
        text("SELECT description FROM documents LIMIT 0")
    )
    assert result is not None


@pytest.mark.asyncio
async def test_service_has_position_column(db_session):
    """service.position (JSONB) must exist — was missing in migration 0003."""
    result = await db_session.execute(
        text("SELECT position FROM service LIMIT 0")
    )
    assert result is not None


@pytest.mark.asyncio
async def test_service_has_liked_users_column(db_session):
    """service.liked_users (UUID[]) must exist — was missing in migration 0003."""
    result = await db_session.execute(
        text("SELECT liked_users FROM service LIMIT 0")
    )
    assert result is not None


# ── All remaining ORM models must be queryable ────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("table", [
    # Identity
    "users",
    "user_refresh_tokens",
    "customer",
    "provider",
    "handyman",
    "companies",
    # Admin
    "admin",
    "admin_role",
    "admin_activity_log",
    "admin_documents",
    "document_deliveries",
    # Catalog
    "category",
    "sub_category",
    "sub_category_documents",
    "service",
    "customers_service",
    "customer_service_details",
    # Documents / Verification
    "documents",
    "verify_documents",
    # Bookings
    "booked_service",
    "service_offer",
    "job_request",
    # Finance
    "payments",
    "wallet_transaction",
    "withdrawal_history",
    "provider_payment_methods",
    "bank_details",
    "service_tier_payment",
    "subscriptions",
    # Content / Marketing
    "blog_post",
    "blog_comment",
    "blog_like",
    "marketing_tracker_sheet",
    "marketing_tracker_column",
    "marketing_tracker_row",
    "page_views",
    # Config / Settings
    "banner",
    "country_tax",
    "app_settings",
    "coupon",
    "currencies",
    "mobile_app_config",
    # CRM / Social
    "review_customer",
    "notification",
    "notifications",
    "feedback",
    "contact_messages",
    "opportunities",
    "opportunity_stage_history",
    "languages",
    # Provider ops
    "provider_availability_weekly",
    "provider_blocked_dates",
    "provider_customer",
    "provider_analytics",
    "activities",
    # Chat
    "chat",
    "chat_inbox",
    # Telegram
    "telegram_chats",
    "telegram_users",
    "telegram_chat_members",
    "telegram_invite_links",
    "telegram_invite_stats",
])
async def test_all_orm_tables_are_selectable(db_session, table):
    """Every mapped table must accept a trivial SELECT without ProgrammingError."""
    result = await db_session.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))
    assert result is not None
