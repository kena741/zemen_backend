"""Integration tests for SMS Compatibility Endpoints.

Endpoints covered:
  - POST /sms/send-otp
  - POST /sms/secure/send-otp
  - POST /sms/verify-otp
  - POST /sms/secure/verify-otp
  - POST /sms/send
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.sms.provider import MockSMSProvider, set_sms_provider


@pytest.fixture(autouse=True)
def mock_sms():
    """Ensure a clean MockSMSProvider is installed for all SMS tests."""
    provider = MockSMSProvider()
    set_sms_provider(provider)
    yield provider
    provider.clear()


@pytest.mark.asyncio
async def test_sms_send_and_verify_otp_standard(client: AsyncClient, mock_sms: MockSMSProvider):
    """POST /sms/send-otp dispatches OTP and /sms/verify-otp verifies successfully."""
    phone = "+251911445566"

    # 1. Dispatch OTP
    send_resp = await client.post(
        "/sms/send-otp",
        json={"recipient": phone, "ttl": 300},
    )
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is True
    verification_id = send_data["verificationId"]
    assert verification_id is not None

    # Retrieve generated code from mock provider
    assert len(mock_sms.dispatched_otps) == 1
    otp_code = mock_sms.dispatched_otps[0]["code"]

    # 2. Verify with wrong code -> 422
    wrong_resp = await client.post(
        "/sms/verify-otp",
        json={"recipient": phone, "code": "000000", "verificationId": verification_id},
    )
    assert wrong_resp.status_code == 422

    # 3. Verify with correct code -> 200
    correct_resp = await client.post(
        "/sms/verify-otp",
        json={"recipient": phone, "code": otp_code, "verificationId": verification_id},
    )
    assert correct_resp.status_code == 200
    assert correct_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_sms_secure_send_and_verify_otp(client: AsyncClient, mock_sms: MockSMSProvider):
    """POST /sms/secure/send-otp and /sms/secure/verify-otp aliases succeed."""
    phone = "+251922334455"

    send_resp = await client.post(
        "/sms/secure/send-otp",
        json={"recipient": phone, "ttl": 300},
    )
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    verification_id = send_data["verificationId"]

    otp_code = mock_sms.dispatched_otps[0]["code"]

    correct_resp = await client.post(
        "/sms/secure/verify-otp",
        json={"recipient": phone, "code": otp_code, "verificationId": verification_id},
    )
    assert correct_resp.status_code == 200
    assert correct_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_sms_send_plain_message(client: AsyncClient, mock_sms: MockSMSProvider):
    """POST /sms/send delivers a plain text notification SMS."""
    payload = {
        "recipient": "+251911998877",
        "message": "Your booking has been confirmed by the provider.",
    }
    resp = await client.post("/sms/send", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert len(mock_sms.dispatched_messages) == 1
    assert mock_sms.dispatched_messages[0]["message"] == payload["message"]
