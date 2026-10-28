"""Chapa verify — env secret only. Never read app_settings.payment.chapa.secretKey."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status

from app.config import settings

_TX_REF = re.compile(r"^[A-Za-z0-9._:-]{6,80}$")


@dataclass(frozen=True)
class ChapaVerifyResult:
    tx_ref: str
    amount: Decimal
    currency: str
    raw_status: str


class ChapaHttp(Protocol):
    async def get(self, url: str, headers: dict[str, str]) -> tuple[int, dict[str, Any]]: ...


class HttpxChapa:
    async def get(self, url: str, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers)
            try:
                body = resp.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            return resp.status_code, body


async def verify_tx_ref(tx_ref: str, *, http: ChapaHttp | None = None) -> ChapaVerifyResult:
    ref = (tx_ref or "").strip()
    if not _TX_REF.match(ref):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tx_ref")
    secret = (settings.CHAPA_SECRET_KEY or "").strip()
    if not secret:
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
