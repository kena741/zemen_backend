"""Repository for Marketing Tracker sheets, columns, and rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from app.domain.content import (
    MarketingColumnDomain,
    MarketingRowDomain,
    MarketingSheetDomain,
)
from app.persistence.sqlalchemy.models.content import (
    MarketingTrackerColumn,
    MarketingTrackerRow,
    MarketingTrackerSheet,
)


class MarketingTrackerRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    # --- Sheets ---

    async def list_sheets(self) -> list[MarketingSheetDomain]:
        stmt = select(MarketingTrackerSheet).order_by(MarketingTrackerSheet.position.asc())
        res = await self.session.execute(stmt)
        return [
            MarketingSheetDomain(
                id=s.id,
                name=s.name,
                position=s.position,
                created_at=s.created_at,
            )
            for s in res.scalars().all()
        ]

    async def count_sheets(self) -> int:
        stmt = select(func.count(MarketingTrackerSheet.id))
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def create_sheet(self, name: str) -> MarketingSheetDomain:
        now = datetime.now(timezone.utc)
        count = await self.count_sheets()
        sheet = MarketingTrackerSheet(
            id=uuid4(),
            name=name,
            position=count + 1,
            created_at=now,
        )
        self.session.add(sheet)
        await self.session.flush()
        return MarketingSheetDomain(
            id=sheet.id,
            name=sheet.name,
            position=sheet.position,
            created_at=sheet.created_at,
        )

    async def rename_sheet(self, sheet_id: UUID, new_name: str) -> MarketingSheetDomain | None:
        stmt = (
            update(MarketingTrackerSheet)
            .where(MarketingTrackerSheet.id == sheet_id)
            .values(name=new_name)
            .returning(MarketingTrackerSheet)
        )
        res = await self.session.execute(stmt)
        sheet = res.scalar_one_or_none()
        return (
            MarketingSheetDomain(
                id=sheet.id,
                name=sheet.name,
                position=sheet.position,
                created_at=sheet.created_at,
            )
            if sheet
            else None
        )

    async def delete_sheet(self, sheet_id: UUID) -> bool:
        # Cascade delete rows and sheet
        await self.session.execute(
            delete(MarketingTrackerRow).where(MarketingTrackerRow.sheet_id == sheet_id)
        )
        del_s = await self.session.execute(
            delete(MarketingTrackerSheet).where(MarketingTrackerSheet.id == sheet_id)
        )
        return bool(del_s.rowcount and del_s.rowcount > 0)

    # --- Columns ---

    async def list_columns(self) -> list[MarketingColumnDomain]:
        stmt = select(MarketingTrackerColumn).order_by(MarketingTrackerColumn.position.asc())
        res = await self.session.execute(stmt)
        return [
            MarketingColumnDomain(
                id=c.id,
                key=c.key,
                label=c.label,
                column_type=c.column_type,
                position=c.position,
                is_system=c.is_system,
                created_at=c.created_at,
            )
            for c in res.scalars().all()
        ]

    async def add_column(
        self,
        key: str,
        label: str,
        column_type: str = "text",
        position: int | None = None,
    ) -> MarketingColumnDomain:
        now = datetime.now(timezone.utc)
        if position is None:
            count_stmt = select(func.count(MarketingTrackerColumn.id))
            res = await self.session.execute(count_stmt)
            position = int(res.scalar_one() or 0) + 1

        col = MarketingTrackerColumn(
            id=uuid4(),
            key=key,
            label=label,
            column_type=column_type,
            position=position,
            is_system=False,
            created_at=now,
        )
        self.session.add(col)
        await self.session.flush()
        return MarketingColumnDomain(
            id=col.id,
            key=col.key,
            label=col.label,
            column_type=col.column_type,
            position=col.position,
            is_system=col.is_system,
            created_at=col.created_at,
        )

    async def delete_column(self, col_id: UUID) -> bool:
        del_c = await self.session.execute(
            delete(MarketingTrackerColumn).where(MarketingTrackerColumn.id == col_id)
        )
        return bool(del_c.rowcount and del_c.rowcount > 0)

    # --- Rows ---

    async def list_rows_for_sheet(self, sheet_id: UUID) -> list[MarketingRowDomain]:
        stmt = (
            select(MarketingTrackerRow)
            .where(MarketingTrackerRow.sheet_id == sheet_id)
            .order_by(MarketingTrackerRow.position.asc())
        )
        res = await self.session.execute(stmt)
        return [
            MarketingRowDomain(
                id=r.id,
                sheet_id=r.sheet_id,
                position=r.position,
                values=r.values or {},
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in res.scalars().all()
        ]

    async def add_row(
        self, sheet_id: UUID, values: dict[str, Any] | None = None
    ) -> MarketingRowDomain:
        now = datetime.now(timezone.utc)
        count_stmt = select(func.count(MarketingTrackerRow.id)).where(
            MarketingTrackerRow.sheet_id == sheet_id
        )
        res = await self.session.execute(count_stmt)
        pos = int(res.scalar_one() or 0) + 1

        row = MarketingTrackerRow(
            id=uuid4(),
            sheet_id=sheet_id,
            position=pos,
            values=values or {},
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return MarketingRowDomain(
            id=row.id,
            sheet_id=row.sheet_id,
            position=row.position,
            values=row.values,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def update_row_values(
        self, row_id: UUID, values: dict[str, Any]
    ) -> MarketingRowDomain | None:
        stmt = select(MarketingTrackerRow).where(MarketingTrackerRow.id == row_id)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        if not row:
            return None

        merged = dict(row.values or {})
        merged.update(values)
        row.values = merged
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return MarketingRowDomain(
            id=row.id,
            sheet_id=row.sheet_id,
            position=row.position,
            values=row.values,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def delete_row(self, row_id: UUID) -> bool:
        del_r = await self.session.execute(
            delete(MarketingTrackerRow).where(MarketingTrackerRow.id == row_id)
        )
        return bool(del_r.rowcount and del_r.rowcount > 0)
