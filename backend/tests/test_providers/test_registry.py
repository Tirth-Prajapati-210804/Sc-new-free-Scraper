from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.providers.base import ProviderAuthError, ProviderQuotaExhaustedError
from app.providers.registry import ProviderRegistry


def make_settings(**overrides) -> MagicMock:
    settings = MagicMock()
    settings.demo_mode = False
    settings.scrapingbee_api_key = ""
    settings.scrapingbee_api_keys = ""
    settings.scrapingbee_base_url = "https://app.scrapingbee.com/api/v1"
    settings.scrapingbee_country_code = "us"
    settings.scrapingbee_user_agent = "flight-harvester/1.0"
    settings.scrapingbee_premium_proxy = False
    settings.scrapingbee_stealth_proxy = False
    settings.scrapingbee_multi_city_debug = False
    settings.provider_timeout_seconds = 30
    settings.provider_max_retries = 3
    settings.provider_concurrency_limit = 2
    settings.provider_min_delay_seconds = 0.5
    for k, v in overrides.items():
        setattr(settings, k, v)
    settings.get_scrapingbee_keys = lambda: [
        key
        for key in [settings.scrapingbee_api_key, *settings.scrapingbee_api_keys.split(",")]
        if isinstance(key, str) and key.strip()
    ]
    return settings


def test_no_providers_when_no_key_and_no_demo() -> None:
    registry = ProviderRegistry(make_settings())
    assert registry.get_enabled() == []


def test_demo_mode_creates_mock_provider() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "demo"


def test_scrapingbee_key_creates_scrapingbee_provider() -> None:
    registry = ProviderRegistry(make_settings(scrapingbee_api_key="bee-key-123"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "scrapingbee"


def test_scrapingbee_debug_flag_is_passed_to_provider() -> None:
    registry = ProviderRegistry(
        make_settings(
            scrapingbee_api_key="bee-key-123",
            scrapingbee_multi_city_debug=True,
        )
    )

    provider = registry.get_enabled()[0]

    assert provider._providers[0]._multi_city_debug is True


def test_demo_mode_takes_priority_over_scrapingbee_key() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True, scrapingbee_api_key="bee-key"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "demo"


def test_status_demo_mode() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    status = registry.status()
    assert status["demo"] == "active"
    assert status["scrapingbee"] == "disabled"


def test_status_scrapingbee_configured() -> None:
    registry = ProviderRegistry(make_settings(scrapingbee_api_key="bee-key"))
    status = registry.status()
    assert status["scrapingbee"] == "configured"


def test_quota_failure_sets_scrapingbee_quota_status_and_disables_provider() -> None:
    registry = ProviderRegistry(make_settings(scrapingbee_api_key="bee-key"))
    registry.report_failure("scrapingbee", ProviderQuotaExhaustedError("quota hit"))

    assert registry.get_enabled() == []
    assert registry.status()["scrapingbee"] == "quota_exhausted"


def test_success_clears_scrapingbee_failure_status() -> None:
    registry = ProviderRegistry(make_settings(scrapingbee_api_key="bee-key"))
    registry.report_failure("scrapingbee", ProviderAuthError("bad key"))
    registry.report_success("scrapingbee")

    providers = registry.get_enabled()
    assert len(providers) == 1
    assert registry.status()["scrapingbee"] == "configured"


def test_status_nothing_configured() -> None:
    registry = ProviderRegistry(make_settings())
    status = registry.status()
    assert status["scrapingbee"] == "disabled"


@pytest.mark.asyncio
async def test_close_all() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    await registry.close_all()
