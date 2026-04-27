from __future__ import annotations

from functools import lru_cache
from urllib.parse import parse_qs, urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "db", "postgres"}

# Hosts that production deploys *must* trust. We always merge these into the
# user's ALLOWED_HOSTS so that a stale env var (e.g. one set on Render before
# we knew the public hostname) cannot lock the API out.
_ALWAYS_ALLOWED_HOSTS = (
    "localhost",
    "127.0.0.1",
    "*.onrender.com",
    "*.vercel.app",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "Flight Price Tracker API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    cors_origin_regex: str = r"^https://([a-z0-9-]+\.)*vercel\.app$"
    allowed_hosts: str = (
        "localhost,127.0.0.1,test,backend,frontend," "*.onrender.com,*.vercel.app"
    )
    expose_api_docs: bool = False

    # Database
    database_url: str

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 120
    admin_email: str
    admin_password: str
    admin_full_name: str = "System Admin"

    # Provider API keys (empty = disabled)
    searchapi_key: str = ""
    searchapi_keys: str = ""
    demo_mode: bool = False

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    scrape_days_ahead: int = 365
    scrape_batch_size: int = 10
    scrape_delay_seconds: float = 1.0
    provider_timeout_seconds: int = 30
    provider_max_retries: int = 3
    provider_concurrency_limit: int = 2
    provider_min_delay_seconds: float = 1.0
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    scrape_rate_limit_attempts: int = 3
    scrape_rate_limit_window_seconds: int = 300

    # Monitoring
    sentry_dsn: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, v: object) -> str:
        return str(v).strip().lower()

    @field_validator("cors_origins", "allowed_hosts", "searchapi_keys", mode="before")
    @classmethod
    def parse_list_to_string(cls, v: object) -> str:
        if isinstance(v, list):
            import json

            return json.dumps(v)
        return str(v)

    @field_validator("searchapi_key", mode="before")
    @classmethod
    def normalize_searchapi_key(cls, v: object) -> str:
        return str(v).strip()

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors(cls, v: str) -> str:
        for origin in cls._parse_csv_or_json(v):
            if origin == "*":
                raise ValueError(
                    "CORS_ORIGINS cannot contain '*'. Specify explicit origins like "
                    "'https://app.example.com' to prevent credentialed-request abuse."
                )
        return v

    @staticmethod
    def _parse_csv_or_json(raw: str) -> list[str]:
        v = raw.strip()
        if v.startswith("["):
            import json

            try:
                parsed = json.loads(v)
            except json.JSONDecodeError:
                return []
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [item.strip() for item in v.split(",") if item.strip()]

    def get_cors_origins(self) -> list[str]:
        return self._parse_csv_or_json(self.cors_origins)

    def get_allowed_hosts(self) -> list[str]:
        configured = self._parse_csv_or_json(self.allowed_hosts)
        # Merge with platform fallbacks so a misconfigured env cannot block
        # standard localhost / Vercel / Render deployments.
        seen: set[str] = set()
        merged: list[str] = []
        for host in (*configured, *_ALWAYS_ALLOWED_HOSTS):
            if host and host not in seen:
                seen.add(host)
                merged.append(host)
        return merged

    def get_searchapi_keys(self) -> list[str]:
        explicit_pool = self._parse_csv_or_json(self.searchapi_keys)
        legacy_field = self._parse_csv_or_json(self.searchapi_key)
        configured = explicit_pool if explicit_pool else legacy_field

        seen: set[str] = set()
        keys: list[str] = []
        for key in configured:
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
        return keys

    @field_validator("debug", "scheduler_enabled", "expose_api_docs", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> bool:
        if isinstance(v, str):
            return v.lower() not in ("false", "0", "release", "production")
        return bool(v)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        parsed = urlparse(v)

        if parsed.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg scheme")

        host = parsed.hostname or ""
        query = parse_qs(parsed.query)

        ssl = (query.get("ssl") or [""])[0]
        sslmode = (query.get("sslmode") or [""])[0]

        # Allow both styles but prefer ssl=true for asyncpg
        if host and host not in _LOCAL_DB_HOSTS:
            if not (ssl in {"true", "require"} or sslmode == "require"):
                raise ValueError(
                    "Remote PostgreSQL connections must include SSL (use ?ssl=true)"
                )

        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. Generate one with: openssl rand -hex 32"
            )
        if "change-me" in v.lower() or "change_me" in v.lower():
            raise ValueError(
                "JWT_SECRET_KEY is still set to the example value. Generate a real secret with: openssl rand -hex 32"
            )
        return v

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("ADMIN_PASSWORD must be at least 12 characters")
        if "change-me" in v.lower() or "change_me" in v.lower():
            raise ValueError(
                "ADMIN_PASSWORD is still set to the example value. Set a real password in .env"
            )
        return v

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment in {"production", "prod"} and self.debug:
            raise ValueError("DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
