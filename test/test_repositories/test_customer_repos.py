"""Unit and mapping tests for Customer repository."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.sqlalchemy.models.identity import Customer
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_customer_repo_to_domain():
    cust_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = Customer(
        id=cust_id,
        user_id=user_id,
        first_name="Tigist",
        last_name="Assefa",
        phone="+251911445566",
        email="tigist@example.com",
        country_code="+251",
        active=True,
        wallet_amount=Decimal("1200.50"),
        signup_source="admin",
        admin_note="VIP customer",
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = CustomerRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == cust_id
    assert domain.full_name == "Tigist Assefa"
    assert domain.phone == "+251911445566"
    assert domain.wallet_amount == 1200.50
    assert domain.admin_note == "VIP customer"

