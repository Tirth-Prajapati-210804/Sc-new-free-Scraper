"""Tests for app.providers.registry — provider registry."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.providers.searchapi import ProviderAuthError, ProviderQuotaExhaustedError
from app.providers.registry import ProviderRegistry


def make_settings(**overrides) -> MagicMock:
    settings = MagicMock()
    settings.demo_mode = False
    settings.searchapi_key = ""
    settings.provider_timeout_seconds = 30
    settings.provider_max_retries = 3
    settings.provider_concurrency_limit = 2
    settings.provider_min_delay_seconds = 1.0
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


def test_searchapi_key_creates_searchapi_provider() -> None:
    registry = ProviderRegistry(make_settings(searchapi_key="test-key-123"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "searchapi"


def test_demo_mode_takes_priority_over_searchapi_key() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True, searchapi_key="test-key"))
    providers = registry.get_enabled()
    assert len(providers) == 1
    assert providers[0].name == "demo"


def test_status_demo_mode() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    status = registry.status()
    assert status["demo"] == "active"
    assert status["searchapi"] == "disabled"


def test_status_searchapi_configured() -> None:
    registry = ProviderRegistry(make_settings(searchapi_key="test-key"))
    status = registry.status()
    assert status["searchapi"] == "configured"


def test_quota_failure_sets_quota_status_and_disables_provider() -> None:
    registry = ProviderRegistry(make_settings(searchapi_key="test-key"))
    registry.report_failure("searchapi", ProviderQuotaExhaustedError("quota hit"))

    assert registry.get_enabled() == []
    assert registry.status()["searchapi"] == "quota_exhausted"


def test_success_clears_provider_failure_status() -> None:
    registry = ProviderRegistry(make_settings(searchapi_key="test-key"))
    registry.report_failure("searchapi", ProviderAuthError("bad key"))
    registry.report_success("searchapi")

    providers = registry.get_enabled()
    assert len(providers) == 1
    assert registry.status()["searchapi"] == "configured"


def test_status_nothing_configured() -> None:
    registry = ProviderRegistry(make_settings())
    status = registry.status()
    assert status["searchapi"] == "disabled"


@pytest.mark.asyncio
async def test_close_all() -> None:
    registry = ProviderRegistry(make_settings(demo_mode=True))
    await registry.close_all()  # should not raise
