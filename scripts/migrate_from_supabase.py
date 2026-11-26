"""Idempotent data migration script from Supabase Postgres to the backend Postgres DB.

Usage examples:
    # Dry-run against Supabase (reads inventory/.env SUPABASE_DATABASE_URL):
    .venv/bin/python scripts/migrate_from_supabase.py --dry-run --skip-auth

    # Full migration to staging (reads STAGING_DATABASE_URL from .env or env):
    .venv/bin/python scripts/migrate_from_supabase.py

    # Migrate specific tables only:
    .venv/bin/python scripts/migrate_from_supabase.py --tables category,sub_category,service
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from uuid import UUID

import asyncpg
import httpx
from dotenv import dotenv_values

from app.core.utils.phone import normalize_ethiopian_phone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("supabase_migration")

# Dependency-ordered public tables to migrate from Supabase.
# `subscriptions` is intentionally omitted because Supabase has 0 rows and its
# legacy Stripe schema differs from the backend's plan-definition schema.
PUBLIC_TABLE_ORDER: list[str] = [
    # 1. Admin & RBAC
    "admin_role",
    "admin",
    "admin_activity_log",
    # 2. Config & Catalog
    "languages",
    "currencies",
    "country_tax",
    "app_settings",
    "mobile_app_config",
    "banner",
    "coupon",
    "category",
    "sub_category",
    "documents",
    "sub_category_documents",
    # 3. Identity & Verification
    "customer",
    "provider",
    "companies",
    "handyman",
    "verify_documents",
    "admin_documents",
    "document_deliveries",
    # 4. Services & Provider Ops
    "service",
    "customers_service",
    "customer_service_details",
    "provider_availability_weekly",
    "provider_blocked_dates",
    "provider_customer",
    "provider_analytics",
    "provider_payment_methods",
    "bank_details",
    # 5. Bookings & Finance
    "job_request",
    "service_offer",
    "booked_service",
    "payments",
    "wallet_transaction",
    "withdrawal_history",
    "service_tier_payment",
    # 6. Social, Content & CRM
    "chat_inbox",
    "chat",
    "review_customer",
    "feedback",
    "contact_messages",
    "notification",
    "notifications",
    "blog_post",
    "blog_comment",
    "blog_like",
    "page_views",
    "marketing_tracker_sheet",
    "marketing_tracker_column",
    "marketing_tracker_row",
    "opportunities",
    "opportunity_stage_history",
    "activities",
]

# Columns present in Supabase that are intentionally absent in the backend.
IGNORED_SOURCE_COLUMNS: dict[str, set[str]] = {
    "customer": {"password"},
    "provider": {"password"},
    "handyman": {"password"},
}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    udt_name: str
    is_nullable: bool


def _load_env_defaults() -> dict[str, str]:
    """Merge .env and inventory/.env without overwriting real environment vars."""
    merged: dict[str, str] = {}
    for path in ("inventory/.env", ".env"):
        if os.path.exists(path):
            for k, v in dotenv_values(path).items():
                if v is not None and v != "":
                    merged[k] = v
    for k, v in os.environ.items():
        if v != "":
            merged[k] = v
    return merged


def _normalize_pg_url(url: str) -> str:
    """Convert SQLAlchemy asyncpg URLs to plain postgresql:// URLs and safely encode passwords."""
    clean = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if "://" not in clean:
        return clean
    scheme, rest = clean.split("://", 1)
    if "@" not in rest:
        return clean
    userinfo, hostpart = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return clean
    user, password = userinfo.split(":", 1)
    # Only encode if not already percent-encoded (avoid double-encoding %2F etc.)
    if any(ch in password for ch in ("?", "#", "/", "@", "&", "=", " ")):
        password = quote(password, safe="")
    return f"{scheme}://{user}:{password}@{hostpart}"


def _mask_pg_url(url: str) -> str:
    """Return host/db portion of Postgres URL without credentials for safe logging."""
    clean = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if "@" in clean:
        return clean.rsplit("@", 1)[-1]
    return clean


def _to_json_str(val: Any) -> Any:
    if val is None or isinstance(val, str):
        return val
    return json.dumps(val)


def _transform_service_tier_payment(row: dict[str, Any]) -> dict[str, Any]:
    """Map Supabase service_tier_payment rows into the aligned backend schema."""
    to_tier = row.get("to_tier_max")
    chapa_status = row.get("chapa_status")
    created_at = row.get("created_at")
    provider_raw = row.get("provider_id")
    return {
        "id": row["id"],
        "provider_id": UUID(str(provider_raw)) if provider_raw else None,
        "user_id": row.get("user_id"),
        "from_tier_max": row.get("from_tier_max"),
        "to_tier_max": to_tier,
        "tier_id": int(to_tier) if to_tier is not None else None,
        "tier_name": f"Tier {to_tier}" if to_tier is not None else "Tier",
        "amount": row["amount"],
        "tx_ref": row.get("tx_ref"),
        "chapa_status": chapa_status,
        "payment_status": chapa_status or "success",
        "created_at": created_at,
        "updated_at": created_at,
    }


def _transform_provider(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("verified_subcategory_ids") is None:
        row["verified_subcategory_ids"] = []
    if row.get("socialLinks") is None:
        row["socialLinks"] = {}
    return row


def _transform_page_views(row: dict[str, Any]) -> dict[str, Any]:
    # Backend stores date_id as TIMESTAMP WITHOUT TIME ZONE
    val = row.get("date_id")
    if val is not None and not hasattr(val, "hour"):
        from datetime import datetime

        row["date_id"] = datetime(val.year, val.month, val.day)
    if "view_count" not in row:
        row["view_count"] = row.get("count") or 0
    if "created_at" not in row:
        row["created_at"] = row.get("updated_at")
    return row


def _transform_contact_messages(row: dict[str, Any]) -> dict[str, Any]:
    """Split Supabase contact_messages.name into staging first_name / last_name."""
    full_name = (row.get("name") or "").strip()
    if full_name:
        parts = full_name.split(None, 1)
        row["first_name"] = parts[0]
        row["last_name"] = parts[1] if len(parts) > 1 else ""
    else:
        row["first_name"] = ""
        row["last_name"] = ""
    return row


ROW_TRANSFORMS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "service_tier_payment": _transform_service_tier_payment,
    "provider": _transform_provider,
    "page_views": _transform_page_views,
    "contact_messages": _transform_contact_messages,
}


async def _get_table_columns(
    conn: asyncpg.Connection, schema: str, table: str
) -> dict[str, ColumnInfo]:
    rows = await conn.fetch(
        """
        SELECT column_name, data_type, udt_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """,
        schema,
        table,
    )
    return {
        r["column_name"]: ColumnInfo(
            name=r["column_name"],
            data_type=r["data_type"],
            udt_name=r["udt_name"],
            is_nullable=(r["is_nullable"] == "YES"),
        )
        for r in rows
    }


async def _get_primary_key_columns(
    conn: asyncpg.Connection, schema: str, table: str
) -> list[str]:
    """Return ordered primary key column names for the given table."""
    rows = await conn.fetch(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = $1
          AND tc.table_name = $2
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        schema,
        table,
    )
    return [r["column_name"] for r in rows]


def _adapt_value(val: Any, col: ColumnInfo | None) -> Any:
    """Adapt Python/asyncpg source values to match target column codecs."""
    if val is None or col is None:
        return val
    if col.udt_name == "jsonb":
        return _to_json_str(val)
    if col.udt_name == "_jsonb" and isinstance(val, list):
        return [_to_json_str(item) for item in val]
    if col.udt_name == "numeric":
        if isinstance(val, str):
            s = val.strip()
            return Decimal(s) if s else None
        if isinstance(val, (int, float)):
            return Decimal(str(val))
    if col.udt_name in ("int2", "int4", "int8"):
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            s = val.strip()
            return int(float(s)) if s else None
    if col.udt_name == "uuid" and isinstance(val, str):
        s = val.strip()
        return UUID(s) if s else None
    return val


async def _fetch_auth_users_via_db(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
            id,
            email,
            phone,
            encrypted_password AS hashed_password,
            COALESCE(is_anonymous, false) AS is_anonymous,
            email_confirmed_at,
            phone_confirmed_at,
            last_sign_in_at,
            banned_until,
            deleted_at,
            created_at,
            updated_at
        FROM auth.users
        ORDER BY created_at ASC
        """
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["is_active"] = d["banned_until"] is None and d["deleted_at"] is None
        out.append(d)
    return out


def _fetch_auth_users_via_api(supabase_url: str, service_role_key: str) -> list[dict[str, Any]]:
    """Fallback when DB user lacks SELECT on auth.users (note: passwords are not exposed)."""
    users: list[dict[str, Any]] = []
    page = 1
    per_page = 1000
    base = supabase_url.rstrip("/")
    headers = {"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"}

    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{base}/auth/v1/admin/users",
                params={"page": page, "per_page": per_page},
                headers=headers,
            )
            resp.raise_for_status()
            batch = resp.json().get("users", [])
            if not batch:
                break
            for u in batch:
                users.append(
                    {
                        "id": UUID(u["id"]),
                        "email": u.get("email") or None,
                        "phone": u.get("phone") or None,
                        "hashed_password": None,
                        "is_active": u.get("banned_until") is None,
                        "is_anonymous": bool(u.get("is_anonymous", False)),
                        "email_confirmed_at": u.get("email_confirmed_at"),
                        "phone_confirmed_at": u.get("phone_confirmed_at"),
                        "last_sign_in_at": u.get("last_sign_in_at"),
                        "banned_until": u.get("banned_until"),
                        "deleted_at": u.get("deleted_at"),
                        "created_at": u.get("created_at"),
                        "updated_at": u.get("updated_at") or u.get("created_at"),
                    }
                )
            if len(batch) < per_page:
                break
            page += 1
    return users


async def _upsert_batch(
    target_conn: asyncpg.Connection,
    table: str,
    columns: list[str],
    pk_columns: list[str],
    col_info: dict[str, ColumnInfo],
    rows: list[dict[str, Any]],
    on_conflict: str,
    batch_size: int,
) -> int:
    if not rows:
        return 0

    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(
        f"${i + 1}::{col_info[c].udt_name}" if c in col_info and col_info[c].udt_name in ("jsonb", "_jsonb") else f"${i + 1}"
        for i, c in enumerate(columns)
    )

    pk_set = set(pk_columns)
    if pk_columns and all(pk in columns for pk in pk_columns):
        pk_target = ", ".join(f'"{c}"' for c in pk_columns)
        if on_conflict == "update":
            non_pk = [c for c in columns if c not in pk_set]
            updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in non_pk)
            conflict_sql = f"ON CONFLICT ({pk_target}) DO UPDATE SET {updates}" if non_pk else f"ON CONFLICT ({pk_target}) DO NOTHING"
        else:
            conflict_sql = f"ON CONFLICT ({pk_target}) DO NOTHING"
    else:
        conflict_sql = ""

    sql = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders}) {conflict_sql}'.strip()

    total = 0
    total_batches = (len(rows) + batch_size - 1) // batch_size
    for batch_idx, start in enumerate(range(0, len(rows), batch_size), start=1):
        chunk = rows[start : start + batch_size]
        records = [
            tuple(_adapt_value(row.get(c), col_info.get(c)) for c in columns)
            for row in chunk
        ]
        try:
            await target_conn.executemany(sql, records)
        except Exception as exc:
            logger.error(
                "[%s] Batch %d/%d (rows %d..%d) failed: %s: %s | columns=%s",
                table,
                batch_idx,
                total_batches,
                start + 1,
                start + len(chunk),
                type(exc).__name__,
                exc,
                columns,
            )
            raise
        total += len(chunk)
        if total_batches > 1:
            logger.info(
                "  [%s] batch %d/%d committed (%d/%d rows)",
                table,
                batch_idx,
                total_batches,
                total,
                len(rows),
            )
    return total


async def _fetch_profile_phones(src_conn: asyncpg.Connection) -> dict[UUID, str]:
    """Build user_id -> normalized phone map from customer and provider tables."""
    phone_map: dict[UUID, str] = {}
    for query in (
        'SELECT user_id, phone FROM "public"."customer" WHERE user_id IS NOT NULL AND phone IS NOT NULL',
        'SELECT user_id, "phoneNumber" AS phone FROM "public"."provider" WHERE user_id IS NOT NULL AND "phoneNumber" IS NOT NULL',
    ):
        rows = await src_conn.fetch(query)
        for r in rows:
            uid = r["user_id"]
            raw_phone = (r["phone"] or "").strip()
            if uid and raw_phone and uid not in phone_map:
                phone_map[uid] = normalize_ethiopian_phone(raw_phone)
    return phone_map


async def migrate_auth_users(
    src_conn: asyncpg.Connection,
    dst_conn: asyncpg.Connection | None,
    env: dict[str, str],
    dry_run: bool,
    on_conflict: str,
    batch_size: int,
) -> tuple[int, int, int]:
    """Migrate auth.users -> public.users. Returns (source_count, before_count, after_count)."""
    users: list[dict[str, Any]]
    try:
        users = await _fetch_auth_users_via_db(src_conn)
        logger.info("[auth.users -> users] fetched %d users via Postgres", len(users))
    except asyncpg.InsufficientPrivilegeError:
        supa_url = env.get("SUPABASE_URL", "")
        service_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supa_url or not service_key:
            raise RuntimeError(
                "Source DB user lacks SELECT on auth.users and SUPABASE_SERVICE_ROLE_KEY is not set. "
                "Provide a privileged --source URL, set SUPABASE_SERVICE_ROLE_KEY, or pass --skip-auth."
            )
        users = _fetch_auth_users_via_api(supa_url, service_key)
        logger.warning(
            "[auth.users -> users] fetched %d users via Auth Admin API (hashed_password is NULL)",
            len(users),
        )

    # Backfill users.phone from customer/provider when auth.users.phone is NULL
    profile_phones = await _fetch_profile_phones(src_conn)
    backfilled = 0
    for u in users:
        if not u.get("phone"):
            fallback_phone = profile_phones.get(u["id"])
            if fallback_phone:
                u["phone"] = fallback_phone
                backfilled += 1
    if backfilled:
        logger.info("[auth.users -> users] backfilled phone from profiles for %d users", backfilled)

    if dry_run or dst_conn is None:
        return len(users), 0, 0

    before_count = int(await dst_conn.fetchval('SELECT count(*) FROM "users"'))
    dst_cols = await _get_table_columns(dst_conn, "public", "users")
    cols = [
        "id",
        "email",
        "phone",
        "hashed_password",
        "is_active",
        "is_anonymous",
        "email_confirmed_at",
        "phone_confirmed_at",
        "last_sign_in_at",
        "banned_until",
        "deleted_at",
        "created_at",
        "updated_at",
    ]
    async with dst_conn.transaction():
        await _upsert_batch(dst_conn, "users", cols, ["id"], dst_cols, users, on_conflict, batch_size)
    after_count = int(await dst_conn.fetchval('SELECT count(*) FROM "users"'))
    logger.info(
        "[auth.users -> users] done: source=%d before=%d inserted=%d after=%d",
        len(users),
        before_count,
        after_count - before_count,
        after_count,
    )
    return len(users), before_count, after_count


async def migrate_public_table(
    src_conn: asyncpg.Connection,
    dst_conn: asyncpg.Connection | None,
    table: str,
    dry_run: bool,
    on_conflict: str,
    batch_size: int,
) -> tuple[int, int, int]:
    """Migrate one public table. Returns (source_count, before_count, after_count)."""
    src_records = await src_conn.fetch(f'SELECT * FROM "public"."{table}"')
    rows = [dict(r) for r in src_records]
    src_count = len(rows)

    transform = ROW_TRANSFORMS.get(table)
    if transform:
        rows = [transform(r) for r in rows]

    if dry_run or dst_conn is None:
        return src_count, 0, 0

    before_count = int(await dst_conn.fetchval(f'SELECT count(*) FROM "{table}"'))
    if not rows:
        return 0, before_count, before_count

    dst_cols = await _get_table_columns(dst_conn, "public", table)
    pk_cols = await _get_primary_key_columns(dst_conn, "public", table)
    ignored = IGNORED_SOURCE_COLUMNS.get(table, set())
    candidate_cols = [c for c in rows[0].keys() if c not in ignored and c in dst_cols]

    async with dst_conn.transaction():
        await _upsert_batch(dst_conn, table, candidate_cols, pk_cols, dst_cols, rows, on_conflict, batch_size)

    after_count = int(await dst_conn.fetchval(f'SELECT count(*) FROM "{table}"'))
    return src_count, before_count, after_count


async def run_migration(args: argparse.Namespace) -> int:
    env = _load_env_defaults()
    source_url = args.source or env.get("SUPABASE_DATABASE_URL")
    target_url = args.target or env.get("STAGING_DATABASE_URL")

    if not source_url:
        logger.error("Missing source URL. Set SUPABASE_DATABASE_URL or pass --source.")
        return 1
    if not args.dry_run and not target_url:
        logger.error("Missing target URL. Set STAGING_DATABASE_URL or pass --target.")
        return 1

    tables = (
        [t.strip() for t in args.tables.split(",") if t.strip()]
        if args.tables
        else PUBLIC_TABLE_ORDER
    )

    logger.info("Connecting to source: %s", _mask_pg_url(source_url))
    src_conn = await asyncpg.connect(_normalize_pg_url(source_url), statement_cache_size=0, timeout=20)
    dst_conn = None
    if not args.dry_run and target_url:
        logger.info("Connecting to target: %s", _mask_pg_url(target_url))
        dst_conn = await asyncpg.connect(_normalize_pg_url(target_url), statement_cache_size=0, timeout=20)

    started_all = time.monotonic()
    try:
        mode = "DRY-RUN" if args.dry_run else f"LIVE (on_conflict={args.on_conflict})"
        logger.info("=== Supabase -> Backend Migration (%s) ===", mode)

        # (table_name, source_count, before_count, after_count, elapsed_s, status)
        summary: list[tuple[str, int, int, int, float, str]] = []
        failed_tables: list[str] = []

        if not args.skip_auth:
            t0 = time.monotonic()
            try:
                s_cnt, b_cnt, a_cnt = await migrate_auth_users(
                    src_conn, dst_conn, env, args.dry_run, args.on_conflict, args.batch_size
                )
                summary.append(("users (auth.users)", s_cnt, b_cnt, a_cnt, time.monotonic() - t0, "ok"))
            except Exception as exc:
                logger.exception("[users (auth.users)] FAILED: %s", exc)
                summary.append(("users (auth.users)", 0, 0, 0, time.monotonic() - t0, "FAILED"))
                failed_tables.append("users")
                if not args.continue_on_error:
                    raise

        total_tables = len(tables)
        for idx, table in enumerate(tables, start=1):
            t0 = time.monotonic()
            logger.info("[%d/%d] Processing '%s'...", idx, total_tables, table)
            try:
                s_cnt, b_cnt, a_cnt = await migrate_public_table(
                    src_conn, dst_conn, table, args.dry_run, args.on_conflict, args.batch_size
                )
                elapsed = time.monotonic() - t0
                summary.append((table, s_cnt, b_cnt, a_cnt, elapsed, "ok"))
                if args.dry_run:
                    logger.info("[%d/%d] '%s': source=%d (%.2fs)", idx, total_tables, table, s_cnt, elapsed)
                else:
                    logger.info(
                        "[%d/%d] '%s': source=%d before=%d inserted=%d target=%d (%.2fs)",
                        idx,
                        total_tables,
                        table,
                        s_cnt,
                        b_cnt,
                        a_cnt - b_cnt,
                        a_cnt,
                        elapsed,
                    )
            except Exception as exc:
                elapsed = time.monotonic() - t0
                logger.exception("[%d/%d] '%s' FAILED after %.2fs: %s", idx, total_tables, table, elapsed, exc)
                summary.append((table, 0, 0, 0, elapsed, "FAILED"))
                failed_tables.append(table)
                if not args.continue_on_error:
                    raise

        total_elapsed = time.monotonic() - started_all
        total_source = sum(x[1] for x in summary)
        total_inserted = sum(max(0, x[3] - x[2]) for x in summary)
        total_target = sum(x[3] for x in summary)

        print("\n=== Migration Summary ===")
        print(f"{'Table':<32} {'Source':>8} {'Before':>8} {'Inserted':>9} {'Target':>8} {'Time(s)':>8} {'Status':>8}")
        print("-" * 87)
        for tbl, s_cnt, b_cnt, a_cnt, el, st in summary:
            if args.dry_run:
                print(f"{tbl:<32} {s_cnt:>8} {'-':>8} {'-':>9} {'-':>8} {el:>8.2f} {st:>8}")
            else:
                ins = a_cnt - b_cnt
                print(f"{tbl:<32} {s_cnt:>8} {b_cnt:>8} {ins:>9} {a_cnt:>8} {el:>8.2f} {st:>8}")
        print("-" * 87)
        if args.dry_run:
            print(f"{'TOTAL':<32} {total_source:>8} {'-':>8} {'-':>9} {'-':>8} {total_elapsed:>8.2f}")
        else:
            print(f"{'TOTAL':<32} {total_source:>8} {'-':>8} {total_inserted:>9} {total_target:>8} {total_elapsed:>8.2f}")

        if failed_tables:
            logger.error("Completed with %d failed table(s): %s", len(failed_tables), ", ".join(failed_tables))
            return 1
        logger.info("Migration completed cleanly in %.2fs.", total_elapsed)
        return 0
    finally:
        await src_conn.close()
        if dst_conn is not None:
            await dst_conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate data from Supabase to backend Postgres.")
    parser.add_argument("--source", help="Source Supabase Postgres URL (defaults to SUPABASE_DATABASE_URL).")
    parser.add_argument("--target", help="Target backend Postgres URL (defaults to STAGING_DATABASE_URL).")
    parser.add_argument("--dry-run", action="store_true", help="Read and validate source data without writing.")
    parser.add_argument("--skip-auth", action="store_true", help="Skip auth.users -> public.users migration.")
    parser.add_argument("--tables", help="Comma-separated list of public tables to migrate.")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Log table failures and continue migrating remaining tables instead of aborting.",
    )
    parser.add_argument(
        "--on-conflict",
        choices=("nothing", "update"),
        default="nothing",
        help="Conflict strategy on id (default: nothing).",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Insert batch size (default: 500).")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_migration(parse_args())))
