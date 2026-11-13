"""Repository for Service entities, review, and featured requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update

from app.domain.catalog import ServiceDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.catalog import Category, Service, SubCategory
from app.persistence.sqlalchemy.models.identity import Provider


class ServiceRepository(BaseRepository[Service, ServiceDomain]):
    model = Service

    def to_domain(
        self,
        entity: Service,
        category_name: str | None = None,
        sub_category_name: str | None = None,
        provider_name: str | None = None,
        provider_email: str | None = None,
    ) -> ServiceDomain:
        return ServiceDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            service_name=entity.service_name,
            description=entity.description,
            address=entity.address,
            category_id=entity.category_id,
            category_name=category_name,
            sub_category_id=entity.sub_category_id,
            sub_category_name=sub_category_name,
            type=entity.type,
            service_location_mode=entity.service_location_mode,
            price=float(entity.price),
            discount=entity.discount,
            pre_payment=entity.pre_payment,
            feature=entity.feature,
            status=entity.status,
            active=entity.active,
            slug=entity.slug,
            service_image=entity.service_image or [],
            video=entity.video,
            duration=entity.duration,
            is_archived=entity.is_archived,
            approved=entity.approved,
            feature_requested_status=entity.feature_requested_status,
            feature_requested_at=entity.feature_requested_at,
            provider_name=provider_name,
            provider_email=provider_email,
            created_at=entity.created_at,
        )

    async def list_services(
        self,
        include_archived: bool = False,
        provider_id: UUID | None = None,
    ) -> list[ServiceDomain]:
        stmt = (
            select(
                Service,
                Category.category_name.label("category_name"),
                SubCategory.sub_category_name.label("sub_category_name"),
                Provider.first_name.label("prov_first"),
                Provider.last_name.label("prov_last"),
                Provider.user_name.label("prov_user"),
                Provider.email.label("prov_email"),
            )
            .outerjoin(Category, Service.category_id == Category.id)
            .outerjoin(SubCategory, Service.sub_category_id == SubCategory.id)
            .outerjoin(Provider, Service.provider_id == Provider.id)
        )

        if not include_archived:
            stmt = stmt.where(Service.is_archived.isnot(True), Service.status.is_(True))
        if provider_id is not None:
            stmt = stmt.where(Service.provider_id == provider_id)

        stmt = stmt.order_by(Service.created_at.desc())
        res = await self.session.execute(stmt)

        items: list[ServiceDomain] = []
        for s, c_name, sc_name, p_first, p_last, p_user, p_email in res.all():
            full = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
            items.append(
                self.to_domain(
                    s,
                    category_name=c_name,
                    sub_category_name=sc_name,
                    provider_name=full,
                    provider_email=p_email,
                )
            )
        return items

    async def get_by_id_enriched(self, service_id: UUID) -> ServiceDomain | None:
        stmt = (
            select(
                Service,
                Category.category_name.label("category_name"),
                SubCategory.sub_category_name.label("sub_category_name"),
                Provider.first_name.label("prov_first"),
                Provider.last_name.label("prov_last"),
                Provider.user_name.label("prov_user"),
                Provider.email.label("prov_email"),
            )
            .outerjoin(Category, Service.category_id == Category.id)
            .outerjoin(SubCategory, Service.sub_category_id == SubCategory.id)
            .outerjoin(Provider, Service.provider_id == Provider.id)
            .where(Service.id == service_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        s, c_name, sc_name, p_first, p_last, p_user, p_email = row
        full = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
        return self.to_domain(
            s,
            category_name=c_name,
            sub_category_name=sc_name,
            provider_name=full,
            provider_email=p_email,
        )

    async def approve_by_provider(self, provider_id: UUID) -> int:
        stmt = (
            update(self.model)
            .where(
                self.model.provider_id == provider_id,
                self.model.is_archived.isnot(True),
                self.model.approved.is_(False),
            )
            .values(approved=True)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        updated_ids = res.all()
        return len(updated_ids)

    async def approve_by_id(self, service_id: UUID) -> bool:
        stmt = (
            update(self.model)
            .where(self.model.id == service_id)
            .values(approved=True)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def update_feature_request(
        self,
        service_id: UUID,
        feature: bool,
        feature_status: str,
    ) -> bool:
        stmt = (
            update(self.model)
            .where(self.model.id == service_id)
            .values(feature=feature, feature_requested_status=feature_status)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def soft_archive(self, service_id: UUID, archive: bool) -> bool:
        values = {
            "is_archived": archive,
            "status": not archive,
            "active": not archive,
        }
        stmt = (
            update(self.model)
            .where(self.model.id == service_id)
            .values(**values)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def count_unapproved_and_featured_pending(self) -> int:
        stmt = select(func.count(self.model.id)).where(
            self.model.is_archived.isnot(True),
            self.model.status.is_(True),
            or_(
                self.model.approved.is_(False),
                self.model.feature_requested_status.ilike("pending"),
            ),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)
