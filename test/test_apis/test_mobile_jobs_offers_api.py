"""Integration tests for Mobile Custom Job Requests and Service Offers APIs."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.jobs import get_job_request_service
from app.api.v1.routers.offers import get_service_offer_service
from app.core.security.deps import AuthContext
from app.domain.booking import BookingDomain
from app.domain.crm import JobRequestDomain
from app.domain.offer import ServiceOfferDomain


@pytest.fixture
def mock_job_service():
    return AsyncMock()


@pytest.fixture
def mock_offer_service():
    return AsyncMock()


def test_customer_job_requests_flow(api_client, mock_job_service):
    user_id = uuid4()
    cust_id = uuid4()
    job_id = str(uuid4())

    mock_job_service.create_or_update_job.return_value = JobRequestDomain(
        id=job_id,
        customer_id=cust_id,
        title="Custom Carpentry",
        description="Build custom shelves",
        price="1200",
    )
    mock_job_service.list_customer_jobs.return_value = [
        JobRequestDomain(
            id=job_id,
            customer_id=cust_id,
            title="Custom Carpentry",
            description="Build custom shelves",
            price="1200",
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_job_request_service] = lambda: mock_job_service

    # Create job request with camelCase payload
    payload = {
        "title": "Custom Carpentry",
        "description": "Build custom shelves",
        "price": "1200",
        "bidPrice": "0",
    }
    res_create = client.post("/api/v1/jobs", json=payload)
    assert res_create.status_code == 201
    assert res_create.json()["title"] == "Custom Carpentry"

    # List customer jobs
    res_list = client.get("/api/v1/jobs?as=customer")
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 1

    # Mark as paid
    res_pay = client.post(f"/api/v1/jobs/{job_id}/pay")
    assert res_pay.status_code == 200
    assert res_pay.json()["is_paid"] is True

    # Delete job
    res_del = client.delete(f"/api/v1/jobs/{job_id}")
    assert res_del.status_code == 204


def test_provider_bidding_flow(api_client, mock_job_service):
    user_id = uuid4()
    prov_id = uuid4()
    job_id = str(uuid4())

    mock_job_service.list_open_jobs.return_value = [
        JobRequestDomain(id=job_id, title="Fix electrical panel", price="2000")
    ]
    mock_job_service.submit_bid.return_value = JobRequestDomain(
        id=job_id,
        title="Fix electrical panel",
        bid_list=[{"providerId": str(prov_id), "bidPrice": "1800"}],
    )

    ctx = AuthContext(
        user_id=user_id,
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_job_request_service] = lambda: mock_job_service

    # Open jobs list
    res_open = client.get("/api/v1/jobs/open")
    assert res_open.status_code == 200
    assert len(res_open.json()["items"]) == 1

    # Submit bid
    res_bid = client.post(
        f"/api/v1/jobs/{job_id}/bid",
        json={"bidPrice": "1800", "message": "Can do it today"},
    )
    assert res_bid.status_code == 200
    assert len(res_bid.json()["bidList"]) == 1


def test_customer_service_offer_flow(api_client, mock_offer_service):
    user_id = uuid4()
    cust_id = uuid4()
    prov_id = uuid4()
    srv_id = uuid4()
    offer_id = uuid4()

    mock_offer_service.create_offer.return_value = ServiceOfferDomain(
        id=offer_id,
        service_id=str(srv_id),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=650.0,
        status="pending",
    )
    mock_offer_service.list_customer_offers.return_value = [
        ServiceOfferDomain(
            id=offer_id,
            service_id=str(srv_id),
            customer_id=str(cust_id),
            provider_id=str(prov_id),
            offered_price=650.0,
            status="pending",
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_service_offer_service] = lambda: mock_offer_service

    # Create offer
    payload = {
        "serviceId": str(srv_id),
        "providerId": str(prov_id),
        "offeredPrice": 650.0,
        "serviceDescription": "Deep clean whole apartment",
        "bookingAddress": {"address": "CMC, Addis Ababa"},
    }
    res_create = client.post("/api/v1/offers", json=payload)
    assert res_create.status_code == 201
    assert res_create.json()["offeredPrice"] == 650.0

    # List customer offers
    res_list = client.get("/api/v1/offers?as=customer")
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 1

    # Cancel offer
    mock_offer_service.cancel_offer.return_value = ServiceOfferDomain(
        id=offer_id,
        service_id=str(srv_id),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=650.0,
        status="cancelled",
    )
    res_cancel = client.post(f"/api/v1/offers/{offer_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"


def test_provider_offer_accept_and_attach_booking(api_client, mock_offer_service):
    user_id = uuid4()
    prov_id = uuid4()
    cust_id = uuid4()
    offer_id = uuid4()
    booking_id = uuid4()

    mock_offer_service.accept_and_book.return_value = BookingDomain(
        id=booking_id,
        provider_id=prov_id,
        customer_id=cust_id,
        service_name="Custom Offer Job",
        status="accepted",
    )
    mock_offer_service.get_offer.return_value = ServiceOfferDomain(
        id=offer_id,
        service_id=str(uuid4()),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=900.0,
        status="accepted",
        booking_id=str(booking_id),
    )

    ctx = AuthContext(
        user_id=user_id,
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_service_offer_service] = lambda: mock_offer_service

    # Accept offer
    res_accept = client.post(f"/api/v1/offers/{offer_id}/accept")
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "accepted"
    assert res_accept.json()["bookingId"] == str(booking_id)

    # Attach booking
    mock_offer_service.attach_booking.return_value = ServiceOfferDomain(
        id=offer_id,
        service_id=str(uuid4()),
        customer_id=str(cust_id),
        provider_id=str(prov_id),
        offered_price=900.0,
        status="accepted",
        booking_id=str(booking_id),
    )
    res_attach = client.post(
        f"/api/v1/offers/{offer_id}/attach-booking",
        json={"bookingId": str(booking_id)},
    )
    assert res_attach.status_code == 200
    assert res_attach.json()["bookingId"] == str(booking_id)

