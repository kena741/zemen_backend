from types import SimpleNamespace
from uuid import uuid4

from app.core.services.booking_service import actor_can_view_booking


def test_customer_owner_can_view():
    customer_id = uuid4()
    booking = SimpleNamespace(
        customer_id=customer_id,
        provider_id=uuid4(),
        customer_user_id=None,
        provider_user_id=None,
    )
    assert actor_can_view_booking(
        booking, user_id=uuid4(), customer_id=customer_id, provider_id=None
    )


def test_provider_owner_can_view():
    provider_id = uuid4()
    booking = SimpleNamespace(
        customer_id=uuid4(),
        provider_id=provider_id,
        customer_user_id=None,
        provider_user_id=None,
    )
    assert actor_can_view_booking(
        booking, user_id=uuid4(), customer_id=None, provider_id=provider_id
    )


def test_stranger_cannot_view():
    booking = SimpleNamespace(
        customer_id=uuid4(),
        provider_id=uuid4(),
        customer_user_id=None,
        provider_user_id=None,
    )
    assert not actor_can_view_booking(
        booking, user_id=uuid4(), customer_id=uuid4(), provider_id=uuid4()
    )
