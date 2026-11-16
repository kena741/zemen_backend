"""Integration tests for Mobile Customer profile endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.customers import get_customer_profile_service
from app.core.security.deps import AuthContext
from app.domain.customer import CustomerDomain


@pytest.fixture
def mock_customer_service():
    return AsyncMock()


def test_get_customer_me(api_client, mock_customer_service):
    user_id = uuid4()
    cust_id = uuid4()
    mock_customer_service.get_profile.return_value = CustomerDomain(
        id=cust_id,
        user_id=user_id,
        first_name="Hana",
        last_name="Mekonnen",
        phone="+251911223344",
        email="hana@example.com",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="hana@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_customer_profile_service] = lambda: mock_customer_service

    res = client.get("/api/v1/customers/me")
    assert res.status_code == 200
    data = res.json()
    assert data["firstName"] == "Hana" or data["first_name"] == "Hana"
    assert data["phone"] == "+251911223344"


def test_update_customer_me(api_client, mock_customer_service):
    user_id = uuid4()
    cust_id = uuid4()
    mock_customer_service.update_profile.return_value = CustomerDomain(
        id=cust_id,
        user_id=user_id,
        first_name="Hana",
        last_name="Updated",
        phone="+251911223344",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="hana@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_customer_profile_service] = lambda: mock_customer_service

    res = client.patch("/api/v1/customers/me", json={"lastName": "Updated"})
    assert res.status_code == 200
    mock_customer_service.update_profile.assert_called_once()


def test_check_phone_registered(api_client, mock_customer_service):
    mock_customer_service.is_phone_registered.return_value = True

    client = api_client()
    client.app.dependency_overrides[get_customer_profile_service] = lambda: mock_customer_service

    res = client.get("/api/v1/customers/check-phone?phone=0911223344")
    assert res.status_code == 200
    data = res.json()
    assert data["isRegistered"] is True or data["is_registered"] is True

