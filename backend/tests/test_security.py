"""Tests for app.core.security — JWT (PyJWT) + password hashing."""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    normalize_email,
    verify_password,
)

_SECRET = "test-secret-key-that-is-at-least-32-characters"
_ALG = "HS256"


# ── Email normalisation ──────────────────────────────────────────────────────

def test_normalize_email_lowercases_and_strips() -> None:
    assert normalize_email("  Admin@Example.COM  ") == "admin@example.com"


def test_normalize_email_empty_string() -> None:
    assert normalize_email("") == ""


# ── Password hashing ─────────────────────────────────────────────────────────

def test_hash_and_verify_password() -> None:
    hashed = hash_password("MySecurePass123!")
    assert hashed != "MySecurePass123!"
    assert verify_password("MySecurePass123!", hashed) is True


def test_verify_wrong_password() -> None:
    hashed = hash_password("CorrectPassword1!")
    assert verify_password("WrongPassword1!", hashed) is False


def test_hash_is_bcrypt_format() -> None:
    hashed = hash_password("test")
    assert hashed.startswith("$2b$12$")


# ── JWT tokens ────────────────────────────────────────────────────────────────

def test_create_and_decode_access_token() -> None:
    token = create_access_token("user-123", _SECRET, _ALG, expires_minutes=60)
    payload = decode_token(token, _SECRET, _ALG)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_decode_token_wrong_secret() -> None:
    token = create_access_token("user-123", _SECRET, _ALG, expires_minutes=60)
    result = decode_token(token, "wrong-secret-that-is-also-32-chars!", _ALG)
    assert result is None


def test_decode_token_expired() -> None:
    token = create_access_token("user-123", _SECRET, _ALG, expires_minutes=-1)
    result = decode_token(token, _SECRET, _ALG)
    assert result is None


def test_decode_token_garbage() -> None:
    result = decode_token("not.a.valid.jwt", _SECRET, _ALG)
    assert result is None


def test_decode_token_empty_string() -> None:
    result = decode_token("", _SECRET, _ALG)
    assert result is None


def test_token_contains_iat_and_nbf() -> None:
    token = create_access_token("user-123", _SECRET, _ALG, expires_minutes=60)
    payload = decode_token(token, _SECRET, _ALG)
    assert "iat" in payload
    assert "nbf" in payload
    assert "exp" in payload


def test_token_wrong_type_rejected() -> None:
    """A token with type != 'access' must be rejected."""
    import jwt

    payload = {
        "sub": "user-123",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "nbf": datetime.now(UTC),
        "type": "refresh",
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALG)
    result = decode_token(token, _SECRET, _ALG)
    assert result is None
