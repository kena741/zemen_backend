from app.api.v1.schemas.booking import BookingCreate
from datetime import datetime, timezone
from uuid import uuid4


def test_booking_create_schema_accepts_aliases():
    body = BookingCreate.model_validate(
        {
            "providerId": str(uuid4()),
            "serviceId": str(uuid4()),
            "bookingDate": datetime.now(timezone.utc).isoformat(),
            "quantity": 1,
            "firstName": "A",
            "lastName": "B",
            "phoneNumber": "0900000000",
        }
    )
    assert body.provider_id is not None
    assert body.quantity == 1
