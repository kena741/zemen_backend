"""Validate Supabase Auth access tokens (HS256 secret or JWKS)."""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.config import settings

_jwks_client: PyJWKClient | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600.0


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_fetched_at
    now = time.time()
    if _jwks_client is None or (now - _jwks_fetched_at) > _JWKS_TTL_SECONDS:
        _jwks_client = PyJWKClient(settings.supabase_jwks_url, cache_keys=True)
        _jwks_fetched_at = now
    return _jwks_client


def decode_supabase_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a Supabase JWT.

    Checks signature, expiry, audience (when configured), and issuer.
    Does not trust role/user id from the request body — only from this payload.
    """
    options = {
        "require": ["exp", "sub"],
        "verify_aud": bool(settings.SUPABASE_JWT_AUDIENCE),
    }
    audience = settings.SUPABASE_JWT_AUDIENCE or None
    issuer = settings.supabase_issuer

    if settings.SUPABASE_JWT_USE_JWKS:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=audience,
            issuer=issuer,
            options=options,
        )

    if not settings.SUPABASE_JWT_SECRET:
        raise jwt.InvalidTokenError("SUPABASE_JWT_SECRET is not configured")

    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience=audience,
        issuer=issuer,
        options=options,
    )


async def probe_jwks() -> bool:
    """Best-effort check that JWKS endpoint is reachable (ops / self-check)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(settings.supabase_jwks_url)
            return resp.status_code == 200
    except Exception:
        return False
