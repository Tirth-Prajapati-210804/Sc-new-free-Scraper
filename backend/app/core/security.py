from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
_ACCESS_TOKEN_TYPE = "access"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
) -> str:
    issued_at = datetime.now(UTC)
    expire = issued_at + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": issued_at,
        "nbf": issued_at,
        "type": _ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str) -> dict | None:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        if payload.get("type") != _ACCESS_TOKEN_TYPE:
            return None
        return payload
    except jwt.PyJWTError:
        return None
