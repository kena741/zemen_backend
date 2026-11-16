"""Unit tests for MobileAuthRepository and phone normalization persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.utils.phone import get_phone_search_variants, normalize_ethiopian_phone
from app.domain.auth import MobileUserCredentialsDomain
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.mobile_auth_repo import MobileAuthRepository
from app.persistence.sqlalchemy.models.identity import Handyman
from app.persistence.sqlalchemy.models.users import User
from test.test_repositories.conftest import RepoMockSession


def test_ethiopian_phone_normalization():
    assert normalize_ethiopian_phone("+251911223344") == "+251911223344"
    assert normalize_ethiopian_phone("251911223344") == "+251911223344"
    assert normalize_ethiopian_phone("0911223344") == "+251911223344"
    assert normalize_ethiopian_phone("911223344") == "+251911223344"
    assert normalize_ethiopian_phone("0711223344") == "+251711223344"

    variants = get_phone_search_variants("0911223344")
    assert "+251911223344" in variants
    assert "0911223344" in variants
    assert "911223344" in variants


@pytest.mark.asyncio
async def test_mobile_auth_repo_get_by_email():
    user_id = uuid4()
    mock_user = User(
        id=user_id,
        email="customer@example.com",
        phone="+251911223344",
        hashed_password="hashed_secret",
        is_active=True,
    )
    session = RepoMockSession(scalar_one_or_none_value=mock_user)
    repo = MobileAuthRepository(session)

    res = await repo.get_by_email("CUSTOMER@example.com")
    assert res is not None
    assert res.id == user_id
    assert res.email == "customer@example.com"


@pytest.mark.asyncio
async def test_mobile_auth_repo_create_user():
    session = RepoMockSession()
    repo = MobileAuthRepository(session)

    user_id = uuid4()
    domain = MobileUserCredentialsDomain(
        id=user_id,
        email="newuser@example.com",
        phone="0911223344",
        hashed_password="hashed_password",
        is_active=True,
    )
    created = await repo.create_user(domain)
    assert created.id == user_id
    assert len(session.added_items) == 1
    assert isinstance(session.added_items[0], User)
    assert session.added_items[0].phone == "+251911223344"


@pytest.mark.asyncio
async def test_handyman_repo_crud():
    handyman_id = uuid4()
    provider_id = uuid4()
    mock_entity = Handyman(
        id=handyman_id,
        provider_id=provider_id,
        first_name="Abebe",
        last_name="Kebede",
        phone_number="+251911111111",
        active=True,
    )
    session = RepoMockSession(scalar_one_or_none_value=mock_entity, scalars_value=[mock_entity])
    repo = HandymanRepository(session)

    item = await repo.get_by_id(handyman_id)
    assert item is not None
    assert item.full_name == "Abebe Kebede"

    items = await repo.list_by_provider(provider_id)
    assert len(items) == 1
    assert items[0].id == handyman_id

