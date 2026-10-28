"""Compare live betegna columns to SQLAlchemy mapped columns.

Reads the MCP dump of information_schema.columns and introspects Base.registry.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    Numeric,
    Text,
    Uuid as SqlUuid,
)

# Ensure app is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.persistence.sqlalchemy.base import Base  # noqa: E402
from app.persistence.sqlalchemy import models as _models  # noqa: F401,E402


DUMP = Path(
    "/Users/DELL/.cursor/projects/Users-DELL-Desktop-zulu-zemen-backend/"
    "agent-tools/50977eac-0b4a-4072-839a-79a5b341ccc8.txt"
)


def extract_live(path: Path) -> list[dict]:
    raw = path.read_text()
    try:
        wrapped = json.loads(raw)
        text = wrapped.get("result", raw)
    except json.JSONDecodeError:
        text = raw
    m = re.search(r"<untrusted-data-[^>]+>\s*(\[.*\])\s*</untrusted-data-", text, re.S)
    if not m:
        raise SystemExit("could not extract JSON from dump")
    return json.loads(m.group(1))


def sa_type_kind(col) -> tuple[str, str | None]:
    """Return (kind, enum_name_or_none) for a SQLAlchemy column type."""
    t = col.type
    if isinstance(t, ENUM):
        return "enum", t.name
    if isinstance(t, (UUID, SAUuid, SqlUuid)):
        return "uuid", None
    if isinstance(t, JSONB):
        return "jsonb", None
    if isinstance(t, ARRAY):
        item = t.item_type
        if isinstance(item, (UUID, SAUuid, SqlUuid)):
            return "array_uuid", None
        if isinstance(item, JSONB):
            return "array_jsonb", None
        if isinstance(item, Text):
            return "array_text", None
        return f"array_{item.__class__.__name__.lower()}", None
    if isinstance(t, Text):
        return "text", None
    if isinstance(t, Boolean):
        return "bool", None
    if isinstance(t, Numeric):
        return "numeric", None
    if isinstance(t, DateTime):
        return "timestamptz" if t.timezone else "timestamp", None
    if isinstance(t, BigInteger):
        return "int8", None
    if isinstance(t, Integer):
        return "int4", None
    if isinstance(t, Float):
        return "float8", None
    return t.__class__.__name__.lower(), None


def live_kind(udt: str, data_type: str) -> tuple[str, str | None]:
    if data_type == "USER-DEFINED":
        return "enum", udt
    mapping = {
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
    }
    return mapping.get(udt, udt), None


def main() -> None:
    live_rows = extract_live(DUMP)
    live: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in live_rows:
        live[r["table_name"]][r["column_name"]] = r

    missing_in_model: list[str] = []
    extra_in_model: list[str] = []
    type_mismatch: list[str] = []
    null_mismatch: list[str] = []
    ok_tables: list[str] = []

    mapped_tables: set[str] = set()
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table.name
        mapped_tables.add(table)
        insp = sa_inspect(cls)
        model_cols = {c.key: c for c in insp.columns}
        # SQLAlchemy key is attribute name; column.name is the DB name
        model_by_db = {c.name: c for c in insp.columns}

        live_cols = live.get(table)
        if live_cols is None:
            extra_in_model.append(f"TABLE {table} mapped but not in live schema")
            continue

        table_issues = 0
        for db_name, col in model_by_db.items():
            if db_name not in live_cols:
                extra_in_model.append(f"{table}.{db_name} (attr={col.key}) in model, not in live")
                table_issues += 1
                continue
            lr = live_cols[db_name]
            mk, menum = sa_type_kind(col)
            lk, lenum = live_kind(lr["udt_name"], lr["data_type"])
            if mk != lk or (mk == "enum" and menum != lenum):
                type_mismatch.append(
                    f"{table}.{db_name}: model={mk}({menum}) live={lk}({lr['udt_name']}) "
                    f"nullable_model={col.nullable} live_null={lr['is_nullable']}"
                )
                table_issues += 1
            live_null = lr["is_nullable"] == "YES"
            if col.nullable != live_null:
                # NOT NULL with a server default is usually OK for reads;
                # flag only when model is NOT NULL and live IS NULL (inserts will fail)
                # or model is NULL and live is NOT NULL without default (writes fail)
                if (not col.nullable and live_null) or (col.nullable and not live_null and not lr.get("column_default")):
                    null_mismatch.append(
                        f"{table}.{db_name}: model.nullable={col.nullable} live={lr['is_nullable']} "
                        f"default={lr.get('column_default')}"
                    )
                    table_issues += 1

        for db_name in live_cols:
            if db_name not in model_by_db:
                missing_in_model.append(f"{table}.{db_name} live {live_cols[db_name]['udt_name']} not mapped")
                table_issues += 1

        if table_issues == 0:
            ok_tables.append(table)

    unmapped_live = sorted(set(live) - mapped_tables)
    print("=== OK tables (names+types match) ===")
    print(", ".join(sorted(ok_tables)) or "(none)")
    print()
    print("=== extra in model (will break SELECT *) ===")
    print("\n".join(extra_in_model) or "(none)")
    print()
    print("=== type mismatches ===")
    print("\n".join(type_mismatch) or "(none)")
    print()
    print("=== nullability mismatches (writes) ===")
    print("\n".join(null_mismatch) or "(none)")
    print()
    print("=== live columns not mapped (SELECT of mapped cols still OK) ===")
    print("\n".join(missing_in_model) or "(none)")
    print()
    print("=== live tables in dump with no mapper ===")
    print(", ".join(unmapped_live) or "(none)")
    print()
    print(
        f"summary: ok={len(ok_tables)} extra={len(extra_in_model)} "
        f"type={len(type_mismatch)} null={len(null_mismatch)} unmapped_cols={len(missing_in_model)}"
    )


if __name__ == "__main__":
    main()
