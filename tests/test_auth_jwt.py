"""Tests for custom JWT token issuance, verification, and password hashing."""

from uuid import uuid4

import pytest

from app.core.auth.hashing import hash_password, verify_password
from app.core.auth.jwt import (
    create_access_token,
    decode_token,
    generate_refresh_token,
    hash_refresh_token,
)


def test_password_hashing():
    raw_password = "super-secret-password-123"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_issuance_and_decoding():
    user_id = uuid4()
    email = "testuser@example.com"
    token = create_access_token(user_id=user_id, email=email, role="customer")

    claims = decode_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["email"] == email
    assert claims["role"] == "customer"
    assert "exp" in claims
    assert "jti" in claims


def test_refresh_token_generation_and_hashing():
    raw_token, token_hash = generate_refresh_token()
    assert len(raw_token) > 40
    assert hash_refresh_token(raw_token) == token_hash

