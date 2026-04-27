from __future__ import annotations

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "jwt_secret_key": "a-secure-test-secret-key-that-is-at-least-32-chars",
        "admin_email": "admin@example.com",
        "admin_password": "StrongPass123!",
    }
    base.update(kwargs)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_debug_true_when_true_string() -> None:
    s = make_settings(debug="true")
    assert s.debug is True


def test_debug_false_when_release() -> None:
    s = make_settings(debug="release")
    assert s.debug is False


def test_debug_false_when_production() -> None:
    s = make_settings(debug="production")
    assert s.debug is False


def test_cors_origins_from_comma_string() -> None:
    s = make_settings(cors_origins="http://localhost:3000,http://localhost:5173")
    assert s.get_cors_origins() == ["http://localhost:3000", "http://localhost:5173"]


def test_allowed_hosts_always_includes_platform_fallbacks() -> None:
    """A narrow ALLOWED_HOSTS env (e.g. stale Render config) must not lock
    the production hostnames out — wildcards for *.onrender.com / *.vercel.app
    are always merged in."""
    s = make_settings(allowed_hosts='["localhost","127.0.0.1"]')
    hosts = s.get_allowed_hosts()
    assert "*.onrender.com" in hosts
    assert "*.vercel.app" in hosts
    # User-configured entries still win on order
    assert hosts.index("localhost") < hosts.index("*.onrender.com")


def test_wildcard_cors_origin_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(cors_origins="*")


def test_non_asyncpg_database_url_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url="postgresql://user:pass@localhost:5432/db")


def test_remote_database_requires_sslmode() -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url="postgresql+asyncpg://user:pass@db.example.com:5432/db")


def test_missing_database_url_raises() -> None:
    field = Settings.model_fields["database_url"]
    assert field.is_required()


def test_missing_jwt_secret_raises() -> None:
    field = Settings.model_fields["jwt_secret_key"]
    assert field.is_required()


def test_short_jwt_secret_raises() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_secret_key="tooshort")


def test_change_me_jwt_raises() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_secret_key="please-change-me-this-is-definitely-32chars!!")


def test_short_admin_password_raises() -> None:
    with pytest.raises(ValidationError):
        make_settings(admin_password="short")


def test_change_me_password_raises() -> None:
    with pytest.raises(ValidationError):
        make_settings(admin_password="change-me-please123")
