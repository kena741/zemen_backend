"""AfroMessage (Afro SMS) Third-Party Provider Implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.core.utils.phone import normalize_ethiopian_phone

logger = logging.getLogger("sms.afromessage")


class AfroSMSProvider:
    """AfroMessage (Afro SMS) HTTP API client implementing the SMSProvider protocol.

    API docs: https://afromessage.com
    - Sends single/bulk SMS and OTP challenges via AfroMessage Gateway.
    - Automatically normalizes Ethiopian recipient phone numbers to +251 format.
    - Handles bearer token authentication, request payload structure, and acknowledgment parsing.
    """

    def __init__(
        self,
        token: str | None = None,
        sender_name: str | None = None,
        identifier_id: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.token = (token or settings.AFRO_SMS_TOKEN or "").strip()
        self.sender_name = (sender_name or settings.AFRO_SMS_SENDER_NAME or "AfroMessage").strip()
        self.identifier_id = (identifier_id or settings.AFRO_SMS_IDENTIFIER_ID or "").strip() or None
        self.base_url = (base_url or settings.AFRO_SMS_BASE_URL or "https://api.afromessage.com/api").rstrip("/")
        self.timeout = timeout

    async def send_sms(self, recipient: str, message: str) -> bool:
        """Send a plain text SMS message to an Ethiopian phone number via AfroMessage."""
        if not self.token:
            logger.warning("AfroMessage token not configured. Unable to dispatch SMS to %s", recipient)
            return False

        norm_phone = normalize_ethiopian_phone(recipient)
        url = f"{self.base_url}/send"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: dict[str, Any] = {
            "to": norm_phone,
            "message": message,
            "sender": self.sender_name,
        }
        if self.identifier_id:
            payload["from"] = self.identifier_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)

                if res.status_code == 200:
                    data = res.json()
                    if data.get("acknowledge") == "success":
                        logger.info("Successfully dispatched SMS to %s via AfroMessage", norm_phone)
                        return True
                    else:
                        errors = data.get("response", {}).get("errors", [])
                        logger.error(
                            "AfroMessage API reported delivery failure to %s: %s",
                            norm_phone,
                            errors or data,
                        )
                        return False
                else:
                    logger.error(
                        "AfroMessage API returned HTTP %s for %s: %s",
                        res.status_code,
                        norm_phone,
                        res.text,
                    )
                    return False
        except httpx.TimeoutException:
            logger.error("Timeout connecting to AfroMessage API while sending SMS to %s", norm_phone)
            return False
        except Exception as exc:
            logger.error("Unexpected error delivering SMS to %s via AfroMessage: %s", norm_phone, exc)
            return False

    async def send_otp(
        self,
        recipient: str,
        code: str,
        message_prefix: str = "Your verification code is",
    ) -> bool:
        """Format an OTP message and dispatch via AfroMessage."""
        prefix = message_prefix.strip()
        message = f"{prefix} {code.strip()}. Valid for 5 minutes."
        return await self.send_sms(recipient=recipient, message=message)

    async def get_balance(self) -> dict[str, Any] | None:
        """Query remaining SMS credits on the AfroMessage account."""
        if not self.token:
            return None

        url = f"{self.base_url}/balance"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.json()
                logger.warning("AfroMessage get_balance returned HTTP %s", res.status_code)
                return None
        except Exception as exc:
            logger.warning("Failed to fetch AfroMessage balance: %s", exc)
            return None
