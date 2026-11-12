"""Repository for Promotional Coupons."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update

from app.domain.settings import CouponDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import Coupon


class CouponRepository(BaseRepository[Coupon, CouponDomain]):
    model = Coupon

    def to_domain(self, entity: Coupon) -> CouponDomain:
        return CouponDomain(
            id=entity.id,
            title=entity.title,
            code=entity.code,
            amount=entity.amount,
            min_amount=entity.min_amount,
            active=entity.active if entity.active is not None else True,
            is_private=entity.is_private or False,
            is_fix=entity.is_fix if entity.is_fix is not None else True,
            expired_at=entity.expired_at,
            created_at=entity.created_at,
        )

    async def list_coupons(self) -> list[CouponDomain]:
        stmt = select(self.model).order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def get_coupon_by_id(self, coupon_id: int) -> CouponDomain | None:
        stmt = select(self.model).where(self.model.id == coupon_id)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

    async def get_by_code(self, code: str) -> CouponDomain | None:
        stmt = select(self.model).where(self.model.code == code)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

    async def create_coupon(self, data: dict[str, Any]) -> CouponDomain:
        if "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc)
        entity = await self.create(data)
        return self.to_domain(entity)

    async def update_coupon(self, coupon_id: int, updates: dict[str, Any]) -> CouponDomain | None:
        clean = {k: v for k, v in updates.items() if v is not None}
        stmt = (
            update(self.model)
            .where(self.model.id == coupon_id)
            .values(**clean)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

    async def delete_coupon(self, coupon_id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == coupon_id)
        res = await self.session.execute(stmt)
        return bool(res.rowcount and res.rowcount > 0)
