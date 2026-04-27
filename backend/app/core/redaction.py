from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api_key=)([^&\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._-]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password=)([^&\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(jwt_secret_key=)([^&\s]+)"), r"\1[REDACTED]"),
    (
        re.compile(r"(?i)(postgresql(?:\+asyncpg)?://)([^:@/\s]+):([^@/\s]+)@"),
        r"\1[REDACTED]:[REDACTED]@",
    ),
]

_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "jwt_secret_key",
    "password",
    "admin_password",
    "database_url",
    "serpapi_key",
}


def redact_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _REPLACEMENTS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            key: ("[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value


def redact_log_event(_: Any, __: Any, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        key: ("[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else redact_value(value))
        for key, value in event_dict.items()
    }
