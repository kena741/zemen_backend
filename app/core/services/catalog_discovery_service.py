"""Service for mobile catalog browsing, discovery, search, likes, banners, and coupons."""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from app.domain.catalog import CategoryDomain, ServiceDomain, SubCategoryDomain
from app.domain.content import BannerDomain
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.settings import CouponDomain
from app.persistence.repositories.banner_repo import BannerRepository
from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.coupon_repo import CouponRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    r = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class CatalogDiscoveryService:
    def __init__(
        self,
        category_repo: CategoryRepository,
        subcategory_repo: SubCategoryRepository,
        service_repo: ServiceRepository,
        banner_repo: BannerRepository,
        coupon_repo: CouponRepository,
    ) -> None:
        self.category_repo = category_repo
        self.subcategory_repo = subcategory_repo
        self.service_repo = service_repo
        self.banner_repo = banner_repo
        self.coupon_repo = coupon_repo

    async def list_categories(self, active_only: bool = True) -> list[CategoryDomain]:
        return await self.category_repo.list_categories(active_only=active_only)

    async def list_subcategories(self, category_id: UUID | None = None) -> list[SubCategoryDomain]:
        if category_id:
            return await self.subcategory_repo.list_by_category_id(category_id)
        return await self.subcategory_repo.list_all()

    async def list_public_services(
        self,
        category_id: UUID | None = None,
        sub_category_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ServiceDomain]:
        return await self.service_repo.list_public_services(
            category_id=category_id,
            sub_category_id=sub_category_id,
            search=search,
            offset=offset,
            limit=limit,
        )

    async def get_service(self, service_id: UUID) -> ServiceDomain:
        service = await self.service_repo.get_by_id_enriched(service_id)
        if not service or service.is_archived or not service.approved:
            raise EntityNotFoundError("Service", service_id)
        return service

    async def list_favourites(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ServiceDomain]:
        return await self.service_repo.list_favourites(user_id=user_id, offset=offset, limit=limit)

    async def toggle_like_service(self, service_id: UUID, user_id: UUID) -> ServiceDomain:
        updated = await self.service_repo.toggle_like(service_id=service_id, user_id=user_id)
        if not updated:
            raise EntityNotFoundError("Service", service_id)
        return updated

    async def list_nearest_services(
        self,
        lat: float,
        lng: float,
        radius_km: float = 50.0,
        category_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ServiceDomain]:
        # Fetch candidate active services
        all_candidates = await self.service_repo.list_public_services(
            category_id=category_id, limit=200
        )
        near: list[tuple[float, ServiceDomain]] = []
        for s in all_candidates:
            s_lat, s_lng = None, None
            if isinstance(s.position, dict):
                s_lat = s.position.get("lat") or s.position.get("latitude")
                s_lng = s.position.get("lng") or s.position.get("longitude")
            elif isinstance(s.location, dict):
                s_lat = s.location.get("lat") or s.location.get("latitude")
                s_lng = s.location.get("lng") or s.location.get("longitude")

            if s_lat is not None and s_lng is not None:
                try:
                    dist = haversine_distance_km(lat, lng, float(s_lat), float(s_lng))
                    if dist <= radius_km:
                        near.append((dist, s))
                except (ValueError, TypeError):
                    continue

        # Sort nearest first
        near.sort(key=lambda x: x[0])
        return [item[1] for item in near[:limit]]

    async def list_banners(self) -> list[BannerDomain]:
        return await self.banner_repo.list_active_banners()

    async def list_coupons(self) -> list[CouponDomain]:
        return await self.coupon_repo.list_coupons()

    async def get_coupon_by_code(self, code: str) -> CouponDomain:
        coupon = await self.coupon_repo.get_by_code(code.strip())
        if not coupon:
            raise EntityNotFoundError("Coupon", code)
        if not coupon.active:
            raise ValidationError("This coupon is inactive or has expired.")
        return coupon

