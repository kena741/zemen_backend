"""Unit and mapping tests for Catalog repositories."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository
from app.persistence.sqlalchemy.models.catalog import Category, Service, SubCategory
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_category_repo_to_domain():
    cat_id = uuid4()
    entity = Category(
        id=cat_id,
        category_name="Home Cleaning",
        image="https://cdn.example.com/cleaning.png",
        active=True,
        description="All residential cleaning services",
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = CategoryRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == cat_id
    assert domain.category_name == "Home Cleaning"
    assert domain.active is True


@pytest.mark.asyncio
async def test_subcategory_repo_to_domain():
    subcat_id = uuid4()
    cat_id = uuid4()
    doc_id = uuid4()
    entity = SubCategory(
        id=subcat_id,
        sub_category_name="Deep Kitchen Cleaning",
        category_id=cat_id,
        is_free=False,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = SubCategoryRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity, category_name="Home Cleaning", document_ids=[doc_id])
    assert domain.id == subcat_id
    assert domain.category_name == "Home Cleaning"
    assert domain.document_ids == [doc_id]


@pytest.mark.asyncio
async def test_service_repo_to_domain():
    srv_id = uuid4()
    prov_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()
    now = datetime.now(timezone.utc)

    entity = Service(
        id=srv_id,
        provider_id=prov_id,
        service_name="Standard Room Cleaning",
        category_id=cat_id,
        category_model={},
        sub_category_id=subcat_id,
        sub_category_model={},
        type="fixed",
        service_location_mode="on_site",
        price=Decimal("450.00"),
        service_image=["https://cdn.example.com/room.png"],
        approved=True,
        created_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = ServiceRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity, category_name="Home Cleaning", provider_name="Abebe Bikila")
    assert domain.id == srv_id
    assert domain.price == 450.00
    assert domain.approved is True
    assert domain.provider_name == "Abebe Bikila"

