"""Repository for Blog Posts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.domain.content import BlogPostDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.content import BlogComment, BlogPost


class BlogPostRepository(BaseRepository[BlogPost, BlogPostDomain]):
    model = BlogPost

    def to_domain(self, entity: BlogPost, comment_count: int = 0) -> BlogPostDomain:
        return BlogPostDomain(
            id=entity.id,
            title=entity.title,
            slug=entity.slug,
            content_html=entity.content_html,
            excerpt=entity.excerpt,
            cover_image=entity.cover_image,
            author_name=entity.author_name,
            status=entity.status,
            published_at=entity.published_at,
            view_count=int(entity.view_count or 0),
            like_count=int(entity.like_count or 0),
            comment_count=comment_count,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_posts_with_comment_count(self) -> list[BlogPostDomain]:
        stmt = (
            select(
                BlogPost,
                func.count(BlogComment.id).label("comment_cnt"),
            )
            .outerjoin(BlogComment, BlogPost.id == BlogComment.post_id)
            .group_by(BlogPost.id)
            .order_by(BlogPost.updated_at.desc())
        )
        res = await self.session.execute(stmt)
        items: list[BlogPostDomain] = []
        for post, cnt in res.all():
            items.append(self.to_domain(post, comment_count=int(cnt or 0)))
        return items

    async def get_by_slug(self, slug: str) -> BlogPostDomain | None:
        stmt = select(self.model).where(self.model.slug == slug)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

