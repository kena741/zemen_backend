"""Repository for Blog Comments."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update

from app.domain.content import BlogCommentDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.content import BlogComment


class BlogCommentRepository(BaseRepository[BlogComment, BlogCommentDomain]):
    model = BlogComment

    def to_domain(self, entity: BlogComment) -> BlogCommentDomain:
        return BlogCommentDomain(
            id=entity.id,
            post_id=entity.post_id,
            full_name=entity.full_name,
            phone=entity.phone,
            body=entity.body,
            status=entity.status,
            created_at=entity.created_at,
        )

    async def list_for_post(self, post_id: UUID) -> list[BlogCommentDomain]:
        stmt = (
            select(self.model)
            .where(self.model.post_id == post_id)
            .order_by(self.model.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(c) for c in res.scalars().all()]

    async def update_status(self, comment_id: UUID, status: str) -> BlogComment | None:
        stmt = (
            update(self.model)
            .where(self.model.id == comment_id)
            .values(status=status)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_comment(self, comment_id: UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == comment_id)
        res = await self.session.execute(stmt)
        return bool(res.rowcount and res.rowcount > 0)

