import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError

from app.api.v1.schemas.booking import BookingCreate, BookingOut
from app.api.v1.schemas.booking_actions import SetBookingStatusBody
from app.api.v1.schemas.admin.requests.bookings import UpdateBookingStatusRequest
from app.api.v1.schemas.admin.requests.providers import PatchCompanyProfileRequest
from app.api.v1.schemas.job import JobRequestCreate


def test_booking_create_strict_payment_status_validation():
    base_data = {
        "providerId": str(uuid4()),
        "serviceId": str(uuid4()),
        "bookingDate": datetime.now(timezone.utc).isoformat(),
    }

    # Default should be "pending_payment"
    b_default = BookingCreate.model_validate(base_data)
    assert b_default.payment_status == "pending_payment"

    # Valid values should succeed
    for valid_val in [
        "pending_payment",
        "payment_approved_by_admin",
        "payment_rejected_by_admin",
        "payment_completed",
        "payment_cancelled",
    ]:
        b = BookingCreate.model_validate({**base_data, "paymentStatus": valid_val})
        assert b.payment_status == valid_val

    # Invalid values (like "pending" or "paid") must fail validation
    for invalid_val in ["pending", "paid", "success", "FAILED"]:
        with pytest.raises(ValidationError):
            BookingCreate.model_validate({**base_data, "paymentStatus": invalid_val})


def test_booking_create_strict_booking_status_validation():
    base_data = {
        "providerId": str(uuid4()),
        "serviceId": str(uuid4()),
        "bookingDate": datetime.now(timezone.utc).isoformat(),
    }

    # Valid booking status
    b = BookingCreate.model_validate({**base_data, "status": "accepted"})
    assert b.status == "accepted"

    # Invalid booking status must fail
    with pytest.raises(ValidationError):
        BookingCreate.model_validate({**base_data, "status": "unknown_status"})


def test_set_booking_status_body_strict_validation():
    # Valid status
    body = SetBookingStatusBody.model_validate({"status": "in_progress"})
    assert body.status == "in_progress"

    # Invalid status must fail
    with pytest.raises(ValidationError):
        SetBookingStatusBody.model_validate({"status": "invalid_flow"})


def test_update_booking_status_request_strict_validation():
    req = UpdateBookingStatusRequest.model_validate({"status": "completed"})
    assert req.status == "completed"

    with pytest.raises(ValidationError):
        UpdateBookingStatusRequest.model_validate({"status": "done"})


def test_provider_company_verification_status_strict_validation():
    req = PatchCompanyProfileRequest.model_validate({"companyVerificationStatus": "approved"})
    assert req.company_verification_status == "approved"

    with pytest.raises(ValidationError):
        PatchCompanyProfileRequest.model_validate({"companyVerificationStatus": "invalid_status"})


def test_job_request_create_strict_status_validation():
    req = JobRequestCreate.model_validate({"status": "pending"})
    assert req.status == "pending"

    with pytest.raises(ValidationError):
        JobRequestCreate.model_validate({"status": "open"})
