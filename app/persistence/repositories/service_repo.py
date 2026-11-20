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
            allows_custom_offer=bool(entity.allows_custom_offer),
            feature_requested_status=entity.feature_requested_status,
            feature_requested_at=entity.feature_requested_at,
            provider_name=provider_name,
            provider_email=provider_email,
            liked_user=list(entity.liked_user or []),
            review_count=entity.review_count or 0,
            review_sum=float(entity.review_sum or 0.0),
            position=entity.position,
            location=entity.location,
            created_at=entity.created_at,
        )

    def to_model(self, domain: ServiceDomain) -> Service:
        from decimal import Decimal
        now = datetime.now(timezone.utc)
        return Service(
            id=domain.id,
            provider_id=domain.provider_id,
            service_name=domain.service_name,
            description=domain.description,
            address=domain.address,
            category_id=domain.category_id,
            category_model={"id": str(domain.category_id), "categoryName": domain.category_name or "Category"},
            sub_category_id=domain.sub_category_id,
            sub_category_model={"id": str(domain.sub_category_id), "subCategoryName": domain.sub_category_name or "SubCategory"},
            type=domain.type,
            service_location_mode=domain.service_location_mode,
            price=Decimal(str(domain.price)),
            discount=domain.discount,
            pre_payment=domain.pre_payment,
            feature=domain.feature,
            status=domain.status,
            active=domain.active if domain.active is not None else True,
            slug=domain.slug,
            service_image=domain.service_image or [],
            video=domain.video,
            duration=domain.duration,
            is_archived=domain.is_archived or False,
            approved=domain.approved,
            allows_custom_offer=False,
            pricing_type=domain.type,
            liked_user=domain.liked_user or [],
            review_count=domain.review_count,
            review_sum=Decimal(str(domain.review_sum)),
            position=domain.position,
            location=domain.location,
            created_at=domain.created_at or now,
        )

    async def list_public_services(
        self,
        category_id: UUID | None = None,
        sub_category_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
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
            .where(
                Service.is_archived.isnot(True),
                Service.status.is_(True),
                Service.approved.is_(True),
                Service.provider_id.isnot(None),
                func.lower(Service.service_name) != "sample service",
            )
        )
        if category_id:
            stmt = stmt.where(Service.category_id == category_id)
        if sub_category_id:
            stmt = stmt.where(Service.sub_category_id == sub_category_id)
        if search:
            stmt = stmt.where(Service.service_name.ilike(f"%{search.strip()}%"))

        stmt = stmt.order_by(Service.created_at.desc()).offset(offset).limit(limit)
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

    async def list_favourites(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ServiceDomain]:
        uid_str = str(user_id)
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
            .where(
                Service.is_archived.isnot(True),
                Service.status.is_(True),
                Service.approved.is_(True),
                Service.liked_user.contains([uid_str]),
            )
            .order_by(Service.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
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

    async def toggle_like(self, service_id: UUID, user_id: UUID) -> ServiceDomain | None:
        stmt = select(Service).where(Service.id == service_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            return None

        uid_str = str(user_id)
        current_likes = list(entity.liked_user or [])
        if uid_str in current_likes:
            current_likes.remove(uid_str)
        else:
            current_likes.append(uid_str)

        entity.liked_user = current_likes
        await self.session.flush()
        return await self.get_by_id_enriched(service_id)

    async def count_active_by_provider(self, provider_id: UUID) -> int:
        stmt = select(func.count(self.model.id)).where(
            self.model.provider_id == provider_id,
            self.model.is_archived.isnot(True),
            self.model.status.is_(True),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def create_service(self, domain: ServiceDomain) -> ServiceDomain:
        entity = self.to_model(domain)
        self.session.add(entity)
        await self.session.flush()
        enriched = await self.get_by_id_enriched(entity.id)
        return enriched or self.to_domain(entity)

    async def update_service_fields(
        self,
        service_id: UUID,
        provider_id: UUID,
        patch: dict[str, Any],
        is_admin_or_system: bool = False,
    ) -> ServiceDomain | None:
        clean = {k: v for k, v in patch.items() if hasattr(self.model, k) and v is not None}
        if not is_admin_or_system:
            # Prevent provider from self-approving or self-featuring
            clean.pop("approved", None)
            clean.pop("feature", None)
        stmt = (
            update(self.model)
            .where(self.model.id == service_id, self.model.provider_id == provider_id)
            .values(**clean)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        if res.scalar_one_or_none() is None:
            return None
        return await self.get_by_id_enriched(service_id)

    async def delete_service(self, service_id: UUID, provider_id: UUID) -> bool:
        stmt = (
            update(self.model)
            .where(self.model.id == service_id, self.model.provider_id == provider_id)
            .values(is_archived=True, status=False, active=False)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

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
