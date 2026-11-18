"""Unit tests for AfroSMSProvider and AfroMessage integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.core.sms.afro_provider import (
    AfroSMSProvider,
    format_afro_phone,
    format_otp_prefix,
)
from app.core.sms.provider import (
    GenericExternalSMSProvider,
    MockSMSProvider,
    get_sms_provider,
    set_sms_provider,
)


@pytest.fixture
def afro_provider():
    return AfroSMSProvider(
        token="test-afro-token-12345",
        sender_name="Zemen Serv",
        identifier_id="e80ad9d8-adf3-463f-80f4-7c4b39f7f164",
        base_url="https://api.afromessage.com/api",
    )


def test_format_afro_phone():
    assert format_afro_phone("0911223344") == "251911223344"
    assert format_afro_phone("+251911223344") == "251911223344"
    assert format_afro_phone("251911223344") == "251911223344"
    assert format_afro_phone("0711223344") == "251711223344"


def test_format_otp_prefix():
    assert format_otp_prefix("") == "Dear Customer, your verification code is "
    assert format_otp_prefix("your code is") == "Dear Customer, your code is "
    assert format_otp_prefix("Dear Customer, verification is") == "Dear Customer, verification is "


@pytest.mark.asyncio
async def test_afro_provider_missing_token_returns_false():
    provider = AfroSMSProvider(token="")
    res = await provider.send_sms("0911223344", "Hello World")
    assert res is False


@pytest.mark.asyncio
async def test_afro_provider_send_sms_success(afro_provider):
    mock_resp = httpx.Response(
        200,
        json={
            "acknowledge": "success",
            "response": {
                "status": "queued",
                "message_id": "msg-123456",
            },
        },
        request=httpx.Request("POST", "https://api.afromessage.com/api/send"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        res = await afro_provider.send_sms("0911223344", "Your code is 123456")

        assert res is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args

        # Verify normalized phone number without '+'
        assert kwargs["json"]["to"] == "251911223344"
        assert kwargs["json"]["message"] == "Your code is 123456"
        assert kwargs["json"]["sender"] == "Zemen Serv"
        assert kwargs["json"]["from"] == "e80ad9d8-adf3-463f-80f4-7c4b39f7f164"
        assert kwargs["headers"]["Authorization"] == "Bearer test-afro-token-12345"


@pytest.mark.asyncio
async def test_afro_provider_send_sms_error_acknowledgment(afro_provider):
    mock_resp = httpx.Response(
        200,
        json={
            "acknowledge": "error",
            "response": {
                "errors": ["Insufficient account credits"],
            },
        },
        request=httpx.Request("POST", "https://api.afromessage.com/api/send"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        res = await afro_provider.send_sms("+251911223344", "Hello")
        assert res is False


@pytest.mark.asyncio
async def test_afro_provider_send_sms_http_error(afro_provider):
    mock_resp = httpx.Response(
        401,
        text="Unauthorized",
        request=httpx.Request("POST", "https://api.afromessage.com/api/send"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        res = await afro_provider.send_sms("+251911223344", "Hello")
        assert res is False


@pytest.mark.asyncio
async def test_afro_provider_send_sms_timeout(afro_provider):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Connection timed out")

        res = await afro_provider.send_sms("0711223344", "Hello")
        assert res is False


@pytest.mark.asyncio
async def test_afro_provider_send_otp_formats_ethio_telecom_prefix(afro_provider):
    with patch.object(afro_provider, "send_sms", new_callable=AsyncMock) as mock_send_sms:
        mock_send_sms.return_value = True

        res = await afro_provider.send_otp(
            recipient="0911223344",
            code="654321",
            message_prefix="your verification code is",
        )

        assert res is True
        mock_send_sms.assert_called_once_with(
            recipient="0911223344",
            message="Dear Customer, your verification code is 654321. Valid for 5 minutes.",
        )


@pytest.mark.asyncio
async def test_afro_provider_challenge_and_verify(afro_provider):
    mock_challenge_resp = httpx.Response(
        200,
        json={
            "acknowledge": "success",
            "response": {
                "verificationId": "v-123",
                "code": "482019",
            },
        },
        request=httpx.Request("GET", "https://api.afromessage.com/api/challenge"),
    )
    mock_verify_resp = httpx.Response(
        200,
        json={
            "acknowledge": "success",
            "response": {"message": "Code verified"},
        },
        request=httpx.Request("GET", "https://api.afromessage.com/api/verify"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Challenge
        mock_get.return_value = mock_challenge_resp
        ch_res = await afro_provider.send_challenge(recipient="0911223344")
        assert ch_res is not None
        assert ch_res["acknowledge"] == "success"
        assert ch_res["response"]["verificationId"] == "v-123"

        # Verify
        mock_get.return_value = mock_verify_resp
        v_res = await afro_provider.verify_challenge(code="482019", verification_id="v-123")
        assert v_res is True


@pytest.mark.asyncio
async def test_afro_provider_get_balance(afro_provider):
    mock_resp = httpx.Response(
        200,
        json={
            "acknowledge": "success",
            "response": {
                "balance": 250.0,
                "currency": "ETB",
            },
        },
        request=httpx.Request("GET", "https://api.afromessage.com/api/balance"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        balance = await afro_provider.get_balance()
        assert balance is not None
        assert balance["acknowledge"] == "success"
        assert balance["response"]["balance"] == 250.0


def test_sms_factory_provider_resolution(monkeypatch):
    import app.core.sms.provider as sms_module
    from app.config import settings

    # Reset singleton state
    sms_module._global_sms_provider = None

    # 1. AfroMessage when token is configured
    monkeypatch.setattr(settings, "SMS_PROVIDER", "afromessage")
    monkeypatch.setattr(settings, "AFRO_SMS_TOKEN", "mock-token-xyz")
    sms_module._global_sms_provider = None
    provider = get_sms_provider()
    assert isinstance(provider, AfroSMSProvider)

    # 2. Mock fallback when token is unset
    sms_module._global_sms_provider = None
    monkeypatch.setattr(settings, "AFRO_SMS_TOKEN", "")
    provider = get_sms_provider()
    assert isinstance(provider, MockSMSProvider)
