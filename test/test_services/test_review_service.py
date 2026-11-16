from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.review_service import ReviewService
from app.domain.booking import BookingDomain
from app.domain.exceptions import EntityConflictError, EntityNotFoundError, ValidationError
from app.domain.review import ReviewCustomerDomain


@pytest.fixture
def mock_review_repo():
    return AsyncMock()


@pytest.fixture
def mock_booking_repo():
    return AsyncMock()


@pytest.fixture
def review_service(mock_review_repo, mock_booking_repo):
    return ReviewService(mock_review_repo, mock_booking_repo)


@pytest.mark.asyncio
async def test_add_review_invalid_rating(review_service):
    cust_id = uuid4()
    with pytest.raises(ValidationError, match="Rating must be between 1.0 and 5.0"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"rating": 6.0, "comment": "Great!"},
        )

    with pytest.raises(ValidationError, match="Rating must be between 1.0 and 5.0"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"rating": 0.5, "comment": "Poor"},
        )


@pytest.mark.asyncio
async def test_add_review_empty_comment(review_service):
    cust_id = uuid4()
    with pytest.raises(ValidationError, match="Review comment is required"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"rating": 5.0, "comment": "   "},
        )


@pytest.mark.asyncio
async def test_add_review_booking_not_found(review_service, mock_booking_repo):
    cust_id = uuid4()
    bid = uuid4()
    mock_booking_repo.get_by_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"booking_id": bid, "rating": 5.0, "comment": "Great!"},
        )


@pytest.mark.asyncio
async def test_add_review_not_booking_owner(review_service, mock_booking_repo):
    cust_id = uuid4()
    other_cust_id = uuid4()
    bid = uuid4()
    mock_booking_repo.get_by_id.return_value = BookingDomain(
        id=bid,
        provider_id=uuid4(),
        customer_id=other_cust_id,
        status="completed",
        service_id=uuid4(),
    )

    with pytest.raises(ValidationError, match="You can only review bookings you ordered"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"booking_id": bid, "rating": 5.0, "comment": "Great!"},
        )


@pytest.mark.asyncio
async def test_add_review_not_completed(review_service, mock_booking_repo):
    cust_id = uuid4()
    bid = uuid4()
    mock_booking_repo.get_by_id.return_value = BookingDomain(
        id=bid,
        provider_id=uuid4(),
        customer_id=cust_id,
        status="pending",
        service_id=uuid4(),
    )

    with pytest.raises(ValidationError, match="You can only review completed bookings"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"booking_id": bid, "rating": 5.0, "comment": "Great!"},
        )


@pytest.mark.asyncio
async def test_add_review_duplicate_guard(review_service, mock_booking_repo, mock_review_repo):
    cust_id = uuid4()
    bid = uuid4()
    mock_booking_repo.get_by_id.return_value = BookingDomain(
        id=bid,
        provider_id=uuid4(),
        customer_id=cust_id,
        status="completed",
        service_id=uuid4(),
    )
    mock_review_repo.get_by_booking_id.return_value = ReviewCustomerDomain(
        id=uuid4(),
        booking_id=bid,
        customer_id=cust_id,
        rating=5.0,
        comment="Earlier review",
    )

    with pytest.raises(EntityConflictError, match="You have already reviewed this booking"):
        await review_service.add_review(
            customer_id=cust_id,
            payload={"booking_id": bid, "rating": 4.5, "comment": "Second review attempt"},
        )


@pytest.mark.asyncio
async def test_add_review_success(review_service, mock_booking_repo, mock_review_repo):
    cust_id = uuid4()
    bid = uuid4()
    sid = uuid4()
    rid = uuid4()
    mock_booking_repo.get_by_id.return_value = BookingDomain(
        id=bid,
        provider_id=uuid4(),
        customer_id=cust_id,
        status="completed",
        service_id=sid,
    )
    mock_review_repo.get_by_booking_id.return_value = None
    mock_review_repo.add_review.return_value = ReviewCustomerDomain(
        id=rid,
        booking_id=bid,
        customer_id=cust_id,
        service_id=sid,
        rating=4.5,
        comment="Excellent work!",
        date=datetime.now(timezone.utc),
    )

    result = await review_service.add_review(
        customer_id=cust_id,
        payload={"booking_id": bid, "rating": 4.5, "comment": "Excellent work!"},
    )

    assert result.id == rid
    assert result.rating == 4.5
    assert result.comment == "Excellent work!"


@pytest.mark.asyncio
async def test_list_service_reviews(review_service, mock_review_repo):
    sid = uuid4()
    mock_review_repo.list_for_service.return_value = [
        ReviewCustomerDomain(
            id=uuid4(),
            service_id=sid,
            rating=5.0,
            comment="Awesome!",
            date=datetime.now(timezone.utc),
        )
    ]

    reviews = await review_service.list_service_reviews(sid, limit=10, offset=0)
    assert len(reviews) == 1
    assert reviews[0].rating == 5.0
    mock_review_repo.list_for_service.assert_awaited_once_with(sid, limit=10, offset=0)


@pytest.mark.asyncio
async def test_get_by_booking_id(review_service, mock_review_repo):
    bid = uuid4()
    mock_review_repo.get_by_booking_id.return_value = ReviewCustomerDomain(
        id=uuid4(),
        booking_id=bid,
        rating=5.0,
        comment="Nice!",
        date=datetime.now(timezone.utc),
    )

    rev = await review_service.get_by_booking_id(bid)
    assert rev is not None
    assert rev.booking_id == bid
    mock_review_repo.get_by_booking_id.assert_awaited_once_with(bid)
