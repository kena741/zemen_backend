"""AfroMessage (Afro SMS) Third-Party Provider Implementation.

Fully compliant with AfroMessage API standards and Ethio Telecom sender regulations.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.core.utils.phone import normalize_ethiopian_phone

logger = logging.getLogger("sms.afromessage")


def format_afro_phone(phone: str) -> str:
    """Format Ethiopian phone number to international format without '+' (e.g. 251911223344)."""
    normalized = normalize_ethiopian_phone(phone)
    return normalized.lstrip("+")


def format_otp_prefix(message_prefix: str) -> str:
    """Ensure template prefix complies with Ethio Telecom sender regulations starting with 'Dear Customer'."""
    prefix = (message_prefix or "").strip()
    if not prefix:
        return "Dear Customer, your verification code is "
    if not prefix.lower().startswith("dear customer"):
        if prefix and prefix[0].isupper() and not prefix.startswith("Dear"):
            prefix = prefix[0].lower() + prefix[1:]
        prefix = f"Dear Customer, {prefix}"
    return f"{prefix} " if not prefix.endswith(" ") else prefix


class AfroSMSProvider:
    """AfroMessage (Afro SMS) HTTP API client implementing the SMSProvider protocol.

    API docs: https://afromessage.com
    - Sends single/bulk SMS and OTP challenges via AfroMessage Gateway.
    - Formats Ethiopian recipient phone numbers to 251XXXXXXXXX (without leading '+').
    - Enforces Ethio Telecom registered template compliance ('Dear Customer, ...').
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
        self.token = (token if token is not None else (settings.AFRO_SMS_TOKEN or "")).strip()
        self.sender_name = (sender_name or settings.AFRO_SMS_SENDER_NAME or "Zemen Serv").strip()
        self.identifier_id = (identifier_id or settings.AFRO_SMS_IDENTIFIER_ID or "").strip() or None
        self.base_url = (base_url or settings.AFRO_SMS_BASE_URL or "https://api.afromessage.com/api").rstrip("/")
        self.timeout = timeout

    async def send_sms(self, recipient: str, message: str, callback: str | None = None) -> bool:
        """Send a plain text SMS message to an Ethiopian phone number via AfroMessage."""
        if not self.token:
            logger.warning("AfroMessage token not configured. Unable to dispatch SMS to %s", recipient)
            return False

        target_phone = format_afro_phone(recipient)
        url = f"{self.base_url}/send"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: dict[str, Any] = {
            "to": target_phone,
            "message": message,
            "sender": self.sender_name,
        }
        if self.identifier_id:
            payload["from"] = self.identifier_id
        if callback:
            payload["callback"] = callback

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)

                if res.status_code == 200:
                    data = res.json()
                    if data.get("acknowledge") == "success":
                        logger.info("Successfully dispatched SMS to %s via AfroMessage", target_phone)
                        return True
                    else:
                        errors = data.get("response", {}).get("errors", [])
                        logger.error(
                            "AfroMessage API reported delivery failure to %s: %s",
                            target_phone,
                            errors or data,
                        )
                        return False
                else:
                    logger.error(
                        "AfroMessage API returned HTTP %s for %s: %s",
                        res.status_code,
                        target_phone,
                        res.text,
                    )
                    return False
        except httpx.TimeoutException:
            logger.error("Timeout connecting to AfroMessage API while sending SMS to %s", target_phone)
            return False
        except Exception as exc:
            logger.error("Unexpected error delivering SMS to %s via AfroMessage: %s", target_phone, exc)
            return False

    async def send_otp(
        self,
        recipient: str,
        code: str,
        message_prefix: str = "Dear Customer, your verification code is ",
    ) -> bool:
        """Format an OTP message and dispatch via AfroMessage /api/send."""
        prefix = format_otp_prefix(message_prefix)
        message = f"{prefix.strip()} {code.strip()}. Valid for 5 minutes."
        return await self.send_sms(recipient=recipient, message=message)

    async def send_challenge(
        self,
        recipient: str,
        code_length: int = 6,
        code_type: int = 0,
        ttl_seconds: int = 300,
        message_prefix: str = "Dear Customer, your verification code is ",
        message_postfix: str = "",
        space_before: int = 1,
        space_after: int = 0,
        callback: str | None = None,
    ) -> dict[str, Any] | None:
        """Trigger native AfroMessage challenge code generation and dispatch via GET /api/challenge."""
        if not self.token:
            return None

        target_phone = format_afro_phone(recipient)
        prefix = format_otp_prefix(message_prefix)
        url = f"{self.base_url}/challenge"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        params: dict[str, Any] = {
            "to": target_phone,
            "sender": self.sender_name,
            "len": code_length,
            "t": code_type,
            "ttl": ttl_seconds,
            "pr": prefix,
            "ps": message_postfix,
            "sb": space_before,
            "sa": space_after,
        }
        if self.identifier_id:
            params["from"] = self.identifier_id
        if callback:
            params["callback"] = callback

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("acknowledge") == "success":
                        return data
                    logger.error("AfroMessage challenge error: %s", data)
                    return None
                logger.error("AfroMessage challenge returned HTTP %s: %s", res.status_code, res.text)
                return None
        except Exception as exc:
            logger.error("AfroMessage challenge failed for %s: %s", target_phone, exc)
            return None

    async def verify_challenge(
        self,
        code: str,
        recipient: str | None = None,
        verification_id: str | None = None,
    ) -> bool:
        """Verify an OTP code directly against AfroMessage's native validation API (GET /api/verify)."""
        if not self.token:
            return False

        url = f"{self.base_url}/verify"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        params: dict[str, Any] = {"code": code.strip()}
        if recipient:
            params["to"] = format_afro_phone(recipient)
        if verification_id:
            params["vc"] = verification_id.strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("acknowledge") == "success"
                return False
        except Exception as exc:
            logger.error("AfroMessage verify_challenge error: %s", exc)
            return False

    async def send_bulk_sms(
        self,
        recipients: list[str | dict[str, str]],
        message: str | None = None,
        campaign: str | None = None,
        create_callback: str | None = None,
        status_callback: str | None = None,
    ) -> dict[str, Any] | None:
        """Send bulk SMS to multiple recipients via AfroMessage (POST /api/bulk_send)."""
        if not self.token:
            return None

        url = f"{self.base_url}/bulk_send"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: dict[str, Any] = {
            "sender": self.sender_name,
            "to": recipients,
        }
        if self.identifier_id:
            payload["from"] = self.identifier_id
        if message:
            payload["message"] = message
        if campaign:
            payload["campaign"] = campaign
        if create_callback:
            payload["createCallback"] = create_callback
        if status_callback:
            payload["statusCallback"] = status_callback

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return data if data.get("acknowledge") == "success" else None
                return None
        except Exception as exc:
            logger.error("AfroMessage bulk send error: %s", exc)
            return None

    async def get_balance(self) -> dict[str, Any] | None:
        """Query remaining SMS credits on the AfroMessage account (GET /api/balance)."""
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
