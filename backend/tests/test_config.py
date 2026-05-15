import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "_env_file": None,
        "environment": "test",
        "app_name": "Test App",
        "secret_key": "a" * 32,
        "jwt_secret_key": "b" * 32,
        "database_url": "postgresql+asyncpg://postgres:secret@localhost/test_db",
        "admin_email": "admin@example.com",
        "admin_password": "AdminPassword123",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_database_url_accepts_local_postgres_without_ssl() -> None:
    settings = _settings(
        database_url="postgresql+asyncpg://postgres:secret@localhost/flights",
    )

    assert settings.database_url == "postgresql+asyncpg://postgres:secret@localhost/flights"


def test_database_url_requires_ssl_for_remote_hosts() -> None:
    with pytest.raises(ValidationError, match="Remote PostgreSQL connections must include SSL"):
        _settings(database_url="postgresql+asyncpg://user:pass@db.example.com/flights")


def test_database_url_accepts_remote_postgres_with_ssl() -> None:
    settings = _settings(
        database_url="postgresql+asyncpg://user:pass@db.example.com/flights?ssl=true",
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@db.example.com/flights?ssl=true"


def test_database_url_rejects_legacy_driver() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL must use the postgresql\\+asyncpg scheme"):
        _settings(database_url="postgres://user:pass@host/dbname")


def test_database_url_rejects_non_postgres_scheme() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL must use the postgresql\\+asyncpg scheme"):
        _settings(database_url="sqlite+aiosqlite:///./test.db")


def test_allowed_hosts_include_platform_fallbacks_in_non_production() -> None:
    settings = _settings(
        environment="development",
        allowed_hosts='["api.example.com"]',
    )

    hosts = settings.get_allowed_hosts()

    assert "api.example.com" in hosts
    assert "*.onrender.com" in hosts
    assert "*.vercel.app" in hosts


def test_allowed_hosts_are_not_broadened_in_production() -> None:
    settings = _settings(
        environment="production",
        allowed_hosts='["api.client.example.com"]',
    )

    assert settings.get_allowed_hosts() == ["api.client.example.com"]


def test_cors_origins_parse_json_list() -> None:
    settings = _settings(
        environment="development",
        allowed_hosts='["localhost"]',
        cors_origins='["http://localhost:5173","https://app.example.com"]',
    )

    assert settings.get_cors_origins() == ["http://localhost:5173", "https://app.example.com"]


def test_cors_origins_accept_csv() -> None:
    settings = _settings(
        environment="development",
        allowed_hosts='["localhost"]',
        cors_origins="http://localhost:5173, https://app.example.com",
    )

    assert settings.get_cors_origins() == ["http://localhost:5173", "https://app.example.com"]


def test_scrapingbee_multi_city_debug_parses_bool() -> None:
    settings = _settings(scrapingbee_multi_city_debug="true")

    assert settings.scrapingbee_multi_city_debug is True
