"""Unit tests for JobRequestService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.job_request_service import JobRequestService
from app.domain.crm import JobRequestDomain
from app.domain.exceptions import EntityNotFoundError, ValidationError


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_customer_repo():
    return AsyncMock()


@pytest.fixture
def job_service(mock_job_repo, mock_customer_repo):
    return JobRequestService(job_repo=mock_job_repo, customer_repo=mock_customer_repo)


@pytest.mark.asyncio
async def test_create_job_success(job_service, mock_job_repo):
    cust_id = uuid4()
    job = JobRequestDomain(
        id=str(uuid4()),
        customer_id=cust_id,
        title="Fix broken roof tile",
        description="Water leaking during heavy rain",
        price="1500",
    )
    mock_job_repo.upsert_job_request.return_value = job

    created = await job_service.create_or_update_job(
        payload={"title": "Fix broken roof tile", "description": "Water leaking", "price": "1500"},
        actor_user_id=uuid4(),
        actor_role="customer",
        customer_id=cust_id,
    )
    assert created.title == "Fix broken roof tile"
    mock_job_repo.upsert_job_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_job_validation_error(job_service):
    with pytest.raises(ValidationError, match="must include a title or description"):
        await job_service.create_or_update_job(
            payload={"price": "100"},
            actor_user_id=uuid4(),
            actor_role="customer",
            customer_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_submit_bid_success(job_service, mock_job_repo):
    job_id = str(uuid4())
    prov_id = uuid4()
    existing = JobRequestDomain(id=job_id, title="Paint walls")
    mock_job_repo.get_by_id.return_value = existing

    updated = JobRequestDomain(
        id=job_id,
        title="Paint walls",
        bid_list=[{"providerId": str(prov_id), "bidPrice": "2000"}],
    )
    mock_job_repo.add_bid.return_value = updated

    res = await job_service.submit_bid(
        job_id=job_id,
        provider_id=prov_id,
        bid_data={"bid_price": "2000", "message": "Can finish in 2 days"},
    )
    assert len(res.bid_list) == 1
    mock_job_repo.add_bid.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_job_success(job_service, mock_job_repo):
    job_id = str(uuid4())
    cust_id = uuid4()
    mock_job_repo.delete_job_by_customer.return_value = True

    assert await job_service.delete_job(job_id, cust_id) is True

    mock_job_repo.delete_job_by_customer.return_value = False
    with pytest.raises(EntityNotFoundError):
        await job_service.delete_job(job_id, cust_id)

