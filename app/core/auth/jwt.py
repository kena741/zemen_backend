"""Custom JWT issuance, verification, and dual-transition token decoding."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from app.config import settings
from app.core.security.supabase_jwt import decode_supabase_token


def create_access_token(
    user_id: UUID,
    email: str | None = None,
    role: str = "authenticated",
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a new access token signed with our internal JWT secret."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def generate_refresh_token() -> tuple[str, str]:
    """Generate a high-entropy refresh token and its SHA256 storage hash.

    Returns:
        (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Hash a raw refresh token to look it up in the database."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT using our own secret, with fallback to Supabase during migration."""
    # 1. Try decoding with our internal secret
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        pass

    # 2. Dual-mode fallback: validate with Supabase JWT verifier if configured
    if settings.SUPABASE_JWT_SECRET or settings.SUPABASE_JWT_USE_JWKS:
        return decode_supabase_token(token)

    raise jwt.InvalidTokenError("Token decoding failed under both internal and Supabase verifiers")

