"""Tests for app.providers.mock — demo/mock flight provider."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.providers.mock import MockProvider


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()


def test_mock_provider_name() -> None:
    assert MockProvider.name == "demo"


def test_mock_provider_is_configured() -> None:
    assert MockProvider().is_configured() is True


@pytest.mark.asyncio
async def test_search_returns_four_results(provider: MockProvider) -> None:
    results = await provider.search_one_way("YVR", "NRT", date.today() + timedelta(days=30))
    assert len(results) == 4


@pytest.mark.asyncio
async def test_search_results_sorted_by_price(provider: MockProvider) -> None:
    results = await provider.search_one_way("YVR", "NRT", date.today() + timedelta(days=30))
    prices = [r.price for r in results]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_search_results_have_required_fields(provider: MockProvider) -> None:
    results = await provider.search_one_way(
        "YVR", "DPS", date.today() + timedelta(days=10), currency="CAD"
    )
    for r in results:
        assert r.price > 0
        assert r.currency == "CAD"
        assert len(r.airline) >= 2
        assert r.provider == "demo"
        assert r.stops >= 0
        assert r.duration_minutes > 0


@pytest.mark.asyncio
async def test_search_is_deterministic(provider: MockProvider) -> None:
    """Same route + date always returns the same prices."""
    d = date.today() + timedelta(days=60)
    r1 = await provider.search_one_way("YVR", "NRT", d)
    r2 = await provider.search_one_way("YVR", "NRT", d)
    assert [r.price for r in r1] == [r.price for r in r2]


@pytest.mark.asyncio
async def test_different_routes_give_different_prices(provider: MockProvider) -> None:
    d = date.today() + timedelta(days=30)
    r1 = await provider.search_one_way("YVR", "NRT", d)
    r2 = await provider.search_one_way("YYZ", "DPS", d)
    assert [r.price for r in r1] != [r.price for r in r2]


@pytest.mark.asyncio
async def test_close_is_noop(provider: MockProvider) -> None:
    await provider.close()  # should not raise


@pytest.mark.asyncio
async def test_prices_within_expected_range(provider: MockProvider) -> None:
    """DPS prices should be within the DPS-specific range."""
    d = date.today() + timedelta(days=20)
    results = await provider.search_one_way("YVR", "DPS", d)
    for r in results:
        assert 900 <= r.price <= 2700  # slightly wider than exact range due to rounding
