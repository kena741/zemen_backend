"""Service for Admin Catalog (Categories, Subcategories) and Service Review."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.catalog import CategoryDomain, ServiceDomain, SubCategoryDomain
from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository


class CatalogAdminService:
    def __init__(
        self,
        category_repo: CategoryRepository,
        subcategory_repo: SubCategoryRepository,
        service_repo: ServiceRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.category_repo = category_repo
        self.subcategory_repo = subcategory_repo
        self.service_repo = service_repo
        self.audit_service = audit_service

    # Categories
    async def list_categories(self) -> list[CategoryDomain]:
        return await self.category_repo.list_all()

    async def create_category(
        self,
        category_name: str,
        image: str | None = None,
        active: bool = True,
        description: str | None = None,
        ctx: AdminContext | None = None,
    ) -> CategoryDomain:
        domain = await self.category_repo.create_category(
            category_name=category_name,
            image=image,
            active=active,
            description=description,
        )
        await self.audit_service.log_action(
            action="create",
            resource_type="category",
            resource_id=str(domain.id),
            summary=f"Created category '{domain.category_name}'",
            ctx=ctx,
        )
        return domain

    async def update_category(
        self,
        category_id: UUID,
        category_name: str | None = None,
        image: str | None = None,
        active: bool | None = None,
        description: str | None = None,
        ctx: AdminContext | None = None,
    ) -> CategoryDomain:
        values: dict[str, Any] = {}
        if category_name is not None:
            values["category_name"] = category_name.strip()
        if image is not None:
            values["image"] = image
        if active is not None:
            values["active"] = active
        if description is not None:
            values["description"] = description

        updated = await self.category_repo.update(category_id, values)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        await self.audit_service.log_action(
            action="update",
            resource_type="category",
            resource_id=str(category_id),
            summary=f"Updated category '{updated.category_name}'",
            ctx=ctx,
        )
        return updated

    async def delete_category(
        self,
        category_id: UUID,
        ctx: AdminContext | None = None,
    ) -> None:
        c = await self.category_repo.get_by_id(category_id)
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        deleted = await self.category_repo.delete(category_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        await self.audit_service.log_action(
            action="delete",
            resource_type="category",
            resource_id=str(category_id),
            summary=f"Deleted category '{c.category_name}'",
            ctx=ctx,
        )

    # Subcategories
    async def list_subcategories(self) -> list[SubCategoryDomain]:
        return await self.subcategory_repo.list_all()

    async def get_document_map(self) -> dict[str, list[str]]:
        return await self.subcategory_repo.get_document_map()

    async def create_subcategory(
        self,
        sub_category_name: str,
        category_id: UUID,
        is_free: bool = False,
        document_ids: list[UUID] | None = None,
        ctx: AdminContext | None = None,
    ) -> SubCategoryDomain:
        domain = await self.subcategory_repo.create_subcategory(
            sub_category_name=sub_category_name,
            category_id=category_id,
            is_free=is_free,
            document_ids=document_ids,
        )
        await self.audit_service.log_action(
            action="create",
            resource_type="subcategory",
            resource_id=str(domain.id),
            summary=f"Created subcategory '{domain.sub_category_name}'",
            ctx=ctx,
        )
        return domain

    async def update_subcategory(
        self,
        subcat_id: UUID,
        sub_category_name: str | None = None,
        category_id: UUID | None = None,
        is_free: bool | None = None,
        document_ids: list[UUID] | None = None,
        ctx: AdminContext | None = None,
    ) -> SubCategoryDomain:
        updated = await self.subcategory_repo.update_subcategory(
            subcat_id=subcat_id,
            sub_category_name=sub_category_name,
            category_id=category_id,
            is_free=is_free,
            document_ids=document_ids,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcategory not found")

        await self.audit_service.log_action(
            action="update",
            resource_type="subcategory",
            resource_id=str(subcat_id),
            summary=f"Updated subcategory '{updated.sub_category_name}'",
            ctx=ctx,
        )
        return updated

    async def delete_subcategory(
        self,
        subcat_id: UUID,
        ctx: AdminContext | None = None,
    ) -> None:
        sc = await self.subcategory_repo.get_by_id(subcat_id)
        if not sc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcategory not found")

        deleted = await self.subcategory_repo.delete(subcat_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcategory not found")

        await self.audit_service.log_action(
            action="delete",
            resource_type="subcategory",
            resource_id=str(subcat_id),
            summary=f"Deleted subcategory '{sc.sub_category_name}'",
            ctx=ctx,
        )

    # Service Review
    async def list_services(
        self,
        include_archived: bool = False,
        provider_id: UUID | None = None,
    ) -> list[ServiceDomain]:
        return await self.service_repo.list_services(
            include_archived=include_archived,
            provider_id=provider_id,
        )

    async def approve_by_provider(
        self,
        provider_id: UUID,
        ctx: AdminContext | None = None,
    ) -> int:
        count = await self.service_repo.approve_by_provider(provider_id)
        await self.audit_service.log_action(
            action="approve_all_services",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Approved {count} unapproved services for provider {provider_id}",
            ctx=ctx,
        )
        return count

    async def approve_by_id(
        self,
        service_id: UUID,
        ctx: AdminContext | None = None,
    ) -> bool:
        ok = await self.service_repo.approve_by_id(service_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        await self.audit_service.log_action(
            action="approve",
            resource_type="service",
            resource_id=str(service_id),
            summary=f"Approved service {service_id}",
            ctx=ctx,
        )
        return True

    async def decide_feature_request(
        self,
        service_id: UUID,
        decision: str,
        ctx: AdminContext | None = None,
    ) -> bool:
        feature_bool = decision == "accept"
        status_val = {
            "accept": "accepted",
            "reject": "rejected",
            "unfeature": "none",
        }.get(decision, "none")

        ok = await self.service_repo.update_feature_request(
            service_id=service_id,
            feature=feature_bool,
            feature_status=status_val,
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        await self.audit_service.log_action(
            action=f"featured_{decision}",
            resource_type="service",
            resource_id=str(service_id),
            summary=f"Featured decision '{decision}' applied to service {service_id}",
            ctx=ctx,
        )
        return True

    async def soft_archive_service(
        self,
        service_id: UUID,
        action: str,
        ctx: AdminContext | None = None,
    ) -> bool:
        should_archive = action == "archive"
        ok = await self.service_repo.soft_archive(service_id, should_archive)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        act_name = "archive" if should_archive else "unarchive"
        await self.audit_service.log_action(
            action=act_name,
            resource_type="service",
            resource_id=str(service_id),
            summary=f"{act_name.capitalize()}d service {service_id}",
            ctx=ctx,
        )
        return True

    async def count_services_badge(self) -> int:
        return await self.service_repo.count_unapproved_and_featured_pending()
