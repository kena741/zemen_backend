"""Chapa integration client — env secret only. Never read app_settings.payment.chapa.secretKey.

Handles transactions initialize, verify, transfers, bank lookup, balance check, and webhook HMAC validation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

_TX_REF = re.compile(r"^[A-Za-z0-9._:-]{6,120}$")


@dataclass(frozen=True)
class ChapaVerifyResult:
    tx_ref: str
    amount: Decimal
    currency: str
    raw_status: str


@dataclass(frozen=True)
class ChapaInitializeResult:
    tx_ref: str
    checkout_url: str
    status: str
    message: str


@dataclass(frozen=True)
class ChapaTransferResult:
    reference: str
    status: str
    message: str
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class ChapaBank:
    id: str
    name: str
    code: str
    swift: str | None = None
    acct_length: int | None = None
    is_rtgs: bool | None = None
    is_mobilemoney: bool | None = None

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> ChapaBank:
        bank_code = str(data.get("bank_code") or data.get("id") or "").strip()
        name = str(data.get("name") or "").strip()
        swift = str(data.get("swift")).strip() if data.get("swift") else None
        code = str(
            data.get("acronym")
            or data.get("code")
            or swift
            or data.get("slug")
            or bank_code
        ).strip()
        acct_len = data.get("acct_length")
        acct_length = int(acct_len) if acct_len is not None and str(acct_len).isdigit() else None
        is_rtgs = bool(data.get("is_rtgs")) if data.get("is_rtgs") is not None else None
        is_mobilemoney = (
            bool(data.get("is_mobilemoney"))
            if data.get("is_mobilemoney") is not None
            else None
        )
        return cls(
            id=bank_code,
            name=name,
            code=code,
            swift=swift,
            acct_length=acct_length,
            is_rtgs=is_rtgs,
            is_mobilemoney=is_mobilemoney,
        )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "swift": self.swift,
            "acct_length": self.acct_length,
            "is_rtgs": self.is_rtgs,
            "is_mobilemoney": self.is_mobilemoney,
        }


class ChapaHttp(Protocol):
    async def get(
        self, url: str, headers: dict[str, str], params: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]: ...

    async def post(
        self, url: str, headers: dict[str, str], json: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]: ...


class HttpxChapa:
    async def get(
        self, url: str, headers: dict[str, str], params: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(url, headers=headers, params=params)
                body = resp.json() if resp.content else {}
            except Exception as exc:
                logger.warning("HttpxChapa GET %s failed: %s", url, exc)
                return 500, {}
            if not isinstance(body, dict):
                body = {}
            return resp.status_code, body

    async def post(
        self, url: str, headers: dict[str, str], json: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(url, headers=headers, json=json)
                body = resp.json() if resp.content else {}
            except Exception as exc:
                logger.warning("HttpxChapa POST %s failed: %s", url, exc)
                return 500, {}
            if not isinstance(body, dict):
                body = {}
            return resp.status_code, body


async def initialize_transaction(
    amount: Decimal | float | str,
    currency: str = "ETB",
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    tx_ref: str | None = None,
    phone_number: str | None = None,
    callback_url: str | None = None,
    return_url: str | None = None,
    customization: dict[str, Any] | None = None,
    *,
    http: ChapaHttp | None = None,
) -> ChapaInitializeResult:
    """Initializes a checkout transaction with Chapa API v1."""
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret and http is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chapa is not configured"
        )

    ref = (tx_ref or f"tx-{secrets.token_hex(8)}").strip()
    if not _TX_REF.match(ref):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tx_ref")

    client = http or HttpxChapa()
    payload: dict[str, Any] = {
        "amount": str(amount),
        "currency": currency,
        "tx_ref": ref,
    }
    if email:
        payload["email"] = email
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if phone_number:
        payload["phone_number"] = phone_number
    if callback_url:
        payload["callback_url"] = callback_url
    if return_url:
        payload["return_url"] = return_url
    if customization:
        payload["customization"] = customization

    code, body = await client.post(
        settings.CHAPA_INITIALIZE_URL,
        {"Authorization": f"Bearer {secret}", "Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
    )

    if code not in (200, 201):
        msg = body.get("message") or "Chapa payment initialization failed"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chapa API error ({code}): {msg}",
        )

    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    checkout_url = data.get("checkout_url")
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chapa checkout URL missing in response",
        )

    return ChapaInitializeResult(
        tx_ref=ref,
        checkout_url=checkout_url,
        status=str(body.get("status") or "success"),
        message=str(body.get("message") or "Hosted Link"),
    )


async def verify_tx_ref(tx_ref: str, *, http: ChapaHttp | None = None) -> ChapaVerifyResult:
    """Verifies a transaction reference with Chapa."""
    ref = (tx_ref or "").strip()
    if not _TX_REF.match(ref):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tx_ref")
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret and http is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chapa is not configured")
    client = http or HttpxChapa()
    code, body = await client.get(
        f"{settings.CHAPA_VERIFY_URL.rstrip('/')}/{ref}",
        {"Authorization": f"Bearer {secret}", "Accept": "application/json"},
    )
    if code != 200:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chapa verification failed")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    ok = body.get("status") == "success" and data.get("status") == "success"
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment not successful")
    amount = Decimal(str(data.get("amount") or "0"))
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chapa amount missing")
    return ChapaVerifyResult(
        tx_ref=str(data.get("tx_ref") or ref),
        amount=amount,
        currency=str(data.get("currency") or "ETB"),
        raw_status=str(data.get("status")),
    )


async def initiate_transfer(
    account_name: str,
    account_number: str,
    amount: Decimal | float | str,
    bank_code: str,
    reference: str,
    currency: str = "ETB",
    *,
    http: ChapaHttp | None = None,
) -> ChapaTransferResult:
    """Transfers funds to a recipient bank account via Chapa."""
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret and http is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chapa is not configured")

    client = http or HttpxChapa()
    payload: dict[str, Any] = {
        "account_name": account_name,
        "account_number": str(account_number),
        "amount": float(amount),
        "bank_code": bank_code,
        "currency": currency,
        "reference": reference,
    }
    code, body = await client.post(
        settings.CHAPA_TRANSFERS_URL,
        {"Authorization": f"Bearer {secret}", "Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
    )
    if code not in (200, 201) or body.get("status") != "success":
        msg = body.get("message") or "Chapa transfer initiation failed"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Chapa API error: {msg}")

    return ChapaTransferResult(
        reference=reference,
        status=str(body.get("status") or "success"),
        message=str(body.get("message") or "Transfer initiated"),
        raw_data=body.get("data") if isinstance(body.get("data"), dict) else {},
    )


async def verify_transfer(
    reference: str,
    *,
    http: ChapaHttp | None = None,
) -> dict[str, Any]:
    """Verifies a payout transfer status with Chapa."""
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret and http is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chapa is not configured")

    client = http or HttpxChapa()
    code, body = await client.get(
        f"{settings.CHAPA_TRANSFERS_URL.rstrip('/')}/verify/{reference}",
        {"Authorization": f"Bearer {secret}", "Accept": "application/json"},
    )
    if code != 200 or body.get("status") != "success":
        msg = body.get("message") or "Chapa transfer verification failed"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chapa transfer verification failed: {msg}",
        )
    return body.get("data") if isinstance(body.get("data"), dict) else body


async def get_banks(*, http: ChapaHttp | None = None) -> list[ChapaBank]:
    """Fetches Ethiopian bank list from Chapa API and parses them into ChapaBank models."""
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret and http is None:
        return []

    client = http or HttpxChapa()
    headers = {"Accept": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    try:
        code, body = await client.get(
            settings.CHAPA_BANKS_URL,
            headers,
        )
        if code == 200:
            data = body.get("data")
            if isinstance(data, list):
                return [
                    ChapaBank.from_api_dict(b)
                    for b in data
                    if isinstance(b, dict)
                ]
    except Exception as exc:
        logger.warning("Failed to fetch banks from Chapa: %s", exc)
    return []


async def get_chapa_balance(*, http: ChapaHttp | None = None) -> dict[str, float]:
    """Fetches real account balance from Chapa API."""
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret:
        return {"available_balance": 0.0, "ledger_balance": 0.0}

    client = http or HttpxChapa()
    try:
        code, body = await client.get(
            settings.CHAPA_BALANCES_URL,
            {"Authorization": f"Bearer {secret}", "Accept": "application/json"},
        )
        if code == 200:
            data = body.get("data") or body.get("balances") or {}
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                return {
                    "available_balance": float(item.get("available_balance", 0.0)),
                    "ledger_balance": float(item.get("ledger_balance", 0.0)),
                }
            if isinstance(data, dict):
                return {
                    "available_balance": float(data.get("available_balance", 0.0)),
                    "ledger_balance": float(data.get("ledger_balance", 0.0)),
                }
    except Exception as exc:
        logger.warning("Failed to fetch balance from Chapa: %s", exc)
    return {"available_balance": 0.0, "ledger_balance": 0.0}


def verify_webhook_signature(
    payload_bytes: bytes,
    signature: str | None,
    secret: str | None = None,
) -> bool:
    """Verifies HMAC SHA-256 signature from Chapa webhook."""
    sig = (signature or "").strip()
    if not sig:
        return False
    key = (secret or settings.CHAPA_WEBHOOK_SECRET or settings.CHAPA_SECRET_KEY or "").strip()
    if not key:
        return False
    computed = hmac.new(key.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed.lower(), sig.lower())
