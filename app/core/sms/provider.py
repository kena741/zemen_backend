"""Pluggable SMS Provider interface and implementations."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import httpx

from app.config import settings

logger = logging.getLogger("sms")


@runtime_checkable
class SMSProvider(Protocol):
    """Protocol defining the SMS provider contract."""

    async def send_otp(self, recipient: str, code: str, message_prefix: str = "Your verification code is") -> bool:
        """Send a one-time password to the specified recipient."""
        ...

    async def send_sms(self, recipient: str, message: str) -> bool:
        """Send a plain text SMS message to the specified recipient."""
        ...


class MockSMSProvider:
    """Mock SMS provider that logs messages and stores dispatched items in memory for testing."""

    def __init__(self) -> None:
        self.dispatched_messages: list[dict[str, str]] = []
        self.dispatched_otps: list[dict[str, str]] = []

    async def send_otp(self, recipient: str, code: str, message_prefix: str = "Your verification code is") -> bool:
        logger.info("[MOCK SMS] OTP to %s: %s %s", recipient, message_prefix, code)
        self.dispatched_otps.append({"recipient": recipient, "code": code, "prefix": message_prefix})
        return True

    async def send_sms(self, recipient: str, message: str) -> bool:
        logger.info("[MOCK SMS] Message to %s: %s", recipient, message)
        self.dispatched_messages.append({"recipient": recipient, "message": message})
        return True

    def clear(self) -> None:
        self.dispatched_messages.clear()
        self.dispatched_otps.clear()


class GenericExternalSMSProvider:
    """Pluggable HTTP gateway adapter for connecting to an external SMS gateway."""

    def __init__(
        self,
        gateway_url: str | None = None,
        api_key: str | None = None,
        sender_id: str = "Zemen",
    ) -> None:
        self.gateway_url = gateway_url or getattr(settings, "SMS_GATEWAY_URL", None)
        self.api_key = api_key or getattr(settings, "SMS_API_KEY", None)
        self.sender_id = sender_id or getattr(settings, "SMS_SENDER_ID", "Zemen")

    async def send_otp(self, recipient: str, code: str, message_prefix: str = "Your verification code is") -> bool:
        message = f"{message_prefix} {code}"
        return await self.send_sms(recipient, message)

    async def send_sms(self, recipient: str, message: str) -> bool:
        if not self.gateway_url:
            logger.warning("No SMS gateway URL configured. Discarding SMS to %s: %s", recipient, message)
            return False

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "recipient": recipient,
            "message": message,
            "sender": self.sender_id,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.gateway_url, json=payload, headers=headers)
                return res.is_success
        except Exception as exc:
            logger.error("Failed to deliver SMS to %s via external provider: %s", recipient, exc)
            return False


_global_sms_provider: SMSProvider | None = None


def get_sms_provider() -> SMSProvider:
    """Dependency injector / factory for obtaining the active SMS provider."""
    global _global_sms_provider
    if _global_sms_provider is None:
        from app.core.sms.afro_provider import AfroSMSProvider

        provider_type = (getattr(settings, "SMS_PROVIDER", None) or "").lower().strip()
        afro_token = (getattr(settings, "AFRO_SMS_TOKEN", None) or "").strip()

        if (provider_type == "afromessage" and afro_token) or (afro_token and provider_type != "mock"):
            _global_sms_provider = AfroSMSProvider()
        elif getattr(settings, "SMS_GATEWAY_URL", None):
            _global_sms_provider = GenericExternalSMSProvider()
        else:
            _global_sms_provider = MockSMSProvider()
    return _global_sms_provider


def set_sms_provider(provider: SMSProvider) -> None:
    """Override the global SMS provider (useful in tests)."""
    global _global_sms_provider
    _global_sms_provider = provider

