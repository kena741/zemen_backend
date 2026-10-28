"""Betegna column names/types must stay compatible with the SQLAlchemy entities."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID, asyncpg
from sqlalchemy import Uuid as SAUuid

from app.api.v1.schemas.booking import BookingOut
from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy import models as _models  # noqa: F401

FIXTURE = Path(__file__).parent / "fixtures" / "betegna_columns.json"

# Legacy hashes / staff notes — never select these through the ORM.
INTENTIONALLY_UNMAPPED = {
    ("customer", "password"),
    ("customer", "admin_note"),
    ("provider", "password"),
    ("provider", "admin_note"),
    ("handyman", "password"),
}


def _kind(col) -> str:
    t = col.type
    if isinstance(t, ENUM):
        return f"enum:{t.name}"
    if isinstance(t, (UUID, SAUuid)):
        return "uuid"
    if isinstance(t, JSONB):
        return "jsonb"
    if isinstance(t, ARRAY):
        item = t.item_type
        if isinstance(item, (UUID, SAUuid)):
            return "array_uuid"
        if isinstance(item, JSONB):
            return "array_jsonb"
        return "array_text"
    name = t.__class__.__name__
    return {
        "Text": "text",
        "Boolean": "bool",
        "Numeric": "numeric",
        "DateTime": "timestamptz" if getattr(t, "timezone", False) else "timestamp",
        "BigInteger": "int8",
        "Integer": "int4",
        "Float": "float8",
        "Uuid": "uuid",
    }.get(name, name.lower())


def _live_kind(udt: str) -> str:
    return {
        "uuid": "uuid",
        "text": "text",
        "bool": "bool",
        "numeric": "numeric",
        "timestamptz": "timestamptz",
        "timestamp": "timestamp",
        "jsonb": "jsonb",
        "int8": "int8",
        "int4": "int4",
        "float8": "float8",
        "_text": "array_text",
        "_jsonb": "array_jsonb",
        "_uuid": "array_uuid",
        "status": "enum:status",
        "payment_status_enum": "enum:payment_status_enum",
        "feature_request_status_enum": "enum:feature_request_status_enum",
        "provider_type": "enum:provider_type",
        "company_verification_status": "enum:company_verification_status",
    }.get(udt, udt)


def _live() -> dict[str, dict[str, dict]]:
    return json.loads(FIXTURE.read_text())


def test_mapped_columns_match_live_betegna_types():
    live = _live()
    extras: list[str] = []
    mismatches: list[str] = []
    for mapper in Base.registry.mappers:
        table = mapper.local_table.name
        live_cols = live[table]
        for col in sa_inspect(mapper.class_).columns:
            if col.name not in live_cols:
                extras.append(f"{table}.{col.name}")
                continue
            got = _kind(col)
            want = _live_kind(live_cols[col.name]["udt"])
            if got != want:
                mismatches.append(f"{table}.{col.name}: model={got} live={want}")
    assert extras == []
    assert mismatches == []


def test_only_intentional_live_columns_are_unmapped():
    live = _live()
    leftover: list[str] = []
    for mapper in Base.registry.mappers:
        table = mapper.local_table.name
        mapped = {c.name for c in sa_inspect(mapper.class_).columns}
        for col in live[table]:
            if col in mapped or (table, col) in INTENTIONALLY_UNMAPPED:
                continue
            leftover.append(f"{table}.{col}")
    assert leftover == []


def test_select_compiles_for_every_mapped_table():
    dialect = asyncpg.dialect()
    for mapper in Base.registry.mappers:
        sql = str(select(mapper.class_).compile(dialect=dialect))
        assert mapper.local_table.name in sql


def test_booking_out_exposes_flutter_booking_model_keys():
    aliases = {
        f.serialization_alias or f.alias or name
        for name, f in BookingOut.model_fields.items()
    }
    for key in (
        "serviceName",
        "bookingDate",
        "paymentCompleted",
        "otp",
        "startTime",
        "endTime",
        "holdTime",
        "extraChargeAmount",
        "extraChargeGst",
        "extraChargeModel",
        "postJob",
        "postJobPayment",
        "prePaymentExtraChargePayment",
        "nextCycleDue",
        "nextCycleNotifiedAt",
    ):
        assert key in aliases
