from app.core.services.profile_service import filter_customer_patch, filter_provider_patch


def test_customer_patch_strips_wallet_and_ids():
    cleaned = filter_customer_patch(
        {
            "first_name": "A",
            "wallet_amount": 9999,
            "id": "x",
            "user_id": "y",
            "active": False,
            "email": "a@b.com",
        }
    )
    assert cleaned == {"first_name": "A", "email": "a@b.com"}


def test_provider_patch_strips_activation_and_wallet():
    cleaned = filter_provider_patch(
        {
            "first_name": "P",
            "wallet_amount": "100",
            "activation_paid": True,
            "service_tier_max": 50,
            "active": False,
            "phone_number": "09",
        }
    )
    assert cleaned == {"first_name": "P", "phone_number": "09"}
