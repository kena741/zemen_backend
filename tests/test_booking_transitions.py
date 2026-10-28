from app.core.services.booking_actions import PROVIDER_TRANSITIONS


def test_pending_can_accept_or_reject():
    assert PROVIDER_TRANSITIONS["pending"] == {"accepted", "rejected"}


def test_completed_has_no_provider_forward():
    assert "completed" not in PROVIDER_TRANSITIONS or not PROVIDER_TRANSITIONS.get(
        "completed"
    )
