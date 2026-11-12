"""Unit and mapping tests for CRM and Job Request repositories."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.persistence.repositories.job_request_repo import JobRequestRepository
from app.persistence.sqlalchemy.models.booking import JobRequest
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_job_request_repo_to_domain():
    cust_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = JobRequest(
        id="jr-12345",
        created_at=now,
        title="Plumbing leak in kitchen",
        description="Water is dripping under the sink",
        price="450.00",
        status="pending",
        accepted=False,
        is_paid=False,
        customer_id=cust_id,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = JobRequestRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(
        entity,
        customer_display_name="Kassahun Tefera",
        customer_display_phone="+251911889900",
    )

    assert domain.id == "jr-12345"
    assert domain.title == "Plumbing leak in kitchen"
    assert domain.price == "450.00"
    assert domain.customer_display_name == "Kassahun Tefera"
    assert domain.customer_display_phone == "+251911889900"


@pytest.mark.asyncio
async def test_job_request_repo_update_action():
    mock_entity = JobRequest(id="jr-12345", status="accepted", accepted=True)
    session = RepoMockSession(scalar_one_or_none_value=mock_entity)
    repo = JobRequestRepository(session)  # type: ignore[arg-type]

    res = await repo.update_job_request("jr-12345", action="accept")
    assert res is not None
    assert len(session.executed_statements) == 1
