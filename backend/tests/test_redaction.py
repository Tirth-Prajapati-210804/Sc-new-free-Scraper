"""Tests for app.core.redaction — secret redaction in logs/text."""
from __future__ import annotations

from app.core.redaction import redact_log_event, redact_text, redact_value


# ── redact_text ──────────────────────────────────────────────────────────────

def test_redact_api_key_in_url() -> None:
    text = "https://serpapi.com/search?api_key=abc123secret&q=flights"
    result = redact_text(text)
    assert "abc123secret" not in result
    assert "[REDACTED]" in result


def test_redact_bearer_token() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
    result = redact_text(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
    assert "[REDACTED]" in result


def test_redact_password_param() -> None:
    text = "password=SuperSecret123!"
    result = redact_text(text)
    assert "SuperSecret123!" not in result


def test_redact_jwt_secret_key() -> None:
    text = "jwt_secret_key=my-super-secret-key"
    result = redact_text(text)
    assert "my-super-secret-key" not in result


def test_redact_database_url() -> None:
    text = "postgresql+asyncpg://admin:secretpass@db.example.com:5432/mydb"
    result = redact_text(text)
    assert "admin" not in result
    assert "secretpass" not in result
    assert "[REDACTED]" in result
    assert "db.example.com" in result  # host should remain


def test_redact_plain_text_unchanged() -> None:
    text = "This is a normal log message with no secrets"
    assert redact_text(text) == text


# ── redact_value ─────────────────────────────────────────────────────────────

def test_redact_value_dict_sensitive_keys() -> None:
    data = {
        "api_key": "secret123",
        "password": "hunter2",
        "serpapi_key": "serpkey",
        "scrapingbee_api_key": "beekey",
        "database_url": "postgresql://user:pass@localhost/db",
        "normal_key": "visible",
    }
    result = redact_value(data)
    assert result["api_key"] == "[REDACTED]"
    assert result["password"] == "[REDACTED]"
    assert result["serpapi_key"] == "[REDACTED]"
    assert result["scrapingbee_api_key"] == "[REDACTED]"
    assert result["database_url"] == "[REDACTED]"
    assert result["normal_key"] == "visible"


def test_redact_value_nested_dict() -> None:
    data = {"config": {"token": "secret", "host": "localhost"}}
    result = redact_value(data)
    assert result["config"]["token"] == "[REDACTED]"
    assert result["config"]["host"] == "localhost"


def test_redact_value_list() -> None:
    data = [{"token": "secret"}, {"host": "localhost"}]
    result = redact_value(data)
    assert result[0]["token"] == "[REDACTED]"
    assert result[1]["host"] == "localhost"


def test_redact_value_string_with_secrets() -> None:
    result = redact_value("api_key=secret123")
    assert "secret123" not in result


def test_redact_value_non_sensitive_passthrough() -> None:
    assert redact_value(42) == 42
    assert redact_value(True) is True
    assert redact_value(None) is None


# ── redact_log_event ─────────────────────────────────────────────────────────

def test_redact_log_event_processor() -> None:
    event = {
        "event": "request",
        "password": "secret123",
        "url": "https://api.example.com?api_key=abc123",
    }
    result = redact_log_event(None, None, event)
    assert result["password"] == "[REDACTED]"
    assert "abc123" not in result["url"]
    assert result["event"] == "request"
