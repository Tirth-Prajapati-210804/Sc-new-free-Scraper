from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.providers.kayak import ProviderAuthError, ProviderQuotaExhaustedError
from app.providers.registry import ProviderRegistry


def make_settings(**overrides) -> MagicMock:
    settings = MagicMock()
    settings.demo_mode = False
    settings.kayak_api_key = ""
    settings.kayak_base_url = "https://sandbox-en-us.kayakaffiliates.com"
    settings.kayak_poll_timeout_seconds = 90
    settings.kayak_poll_interval_seconds = 2.0
    settings.kayak_user_agent = "flight-harvester/1.0"
    settings.kayak_original_client_ip = ""
    settings.provider_timeout_seconds = 30
    settings.provider_max_retries = 3
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def test_no_providers_when_no_key_and_no_demo() -> None:
    registry = ProviderRegistry(make_settings())
    assert registry.get_enabled() == []


def test_demo_mode_creates_mock_provider() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "demo"


def test_kayak_key_creates_kayak_provider() -> None:
    registry = ProviderRegistry(make_settings(kayak_api_key="test-key-123"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "kayak"


def test_demo_mode_takes_priority_over_kayak_key() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True, kayak_api_key="test-key"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "demo"


def test_status_demo_mode() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    status = registry.status()
    assert status["demo"] == "active"
    assert status["kayak"] == "disabled"


def test_status_kayak_configured() -> None:
    registry = ProviderRegistry(make_settings(kayak_api_key="test-key"))
    status = registry.status()
    assert status["kayak"] == "configured"


def test_quota_failure_sets_quota_status_and_disables_provider() -> None:
    registry = ProviderRegistry(make_settings(kayak_api_key="test-key"))
    registry.report_failure("kayak", ProviderQuotaExhaustedError("quota hit"))

    assert registry.get_enabled() == []
    assert registry.status()["kayak"] == "quota_exhausted"


def test_success_clears_provider_failure_status() -> None:
    registry = ProviderRegistry(make_settings(kayak_api_key="test-key"))
    registry.report_failure("kayak", ProviderAuthError("bad key"))
    registry.report_success("kayak")

    providers = registry.get_enabled()
    assert len(providers) == 1
    assert registry.status()["kayak"] == "configured"


def test_status_nothing_configured() -> None:
    registry = ProviderRegistry(make_settings())
    status = registry.status()
    assert status["kayak"] == "disabled"


@pytest.mark.asyncio
async def test_close_all() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    await registry.close_all()
