from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.base import ProviderResult
from app.services.price_collector import CollectionResult, PriceCollector


# ── helpers ──────────────────────────────────────────────────────────────────

def make_result(price: float, airline: str = "AC", provider: str = "serpapi") -> ProviderResult:
    return ProviderResult(
        price=price,
        currency="CAD",
        airline=airline,
        deep_link="https://example.com",
        provider=provider,
    )


def make_provider(name: str, results: list[ProviderResult]) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.search_one_way = AsyncMock(return_value=results)
    return p


def make_session_factory(session: AsyncMock) -> MagicMock:
    """Return a mock async_sessionmaker that yields the given session."""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return factory


ROUTE_ID = uuid.uuid4()
TODAY = date.today()
DEPART = TODAY + timedelta(days=30)


# ── unit tests (mock session + providers) ────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_single_date_returns_cheapest() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    provider = make_provider("serpapi", [make_result(1500), make_result(2000)])
    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[provider],
    )

    # Patch _upsert_cheapest so we don't need a real DB
    collector._upsert_cheapest = AsyncMock()

    result = await collector.collect_single_date("YYZ", "NRT", DEPART, ROUTE_ID)

    assert isinstance(result, CollectionResult)
    assert result.cheapest is not None
    assert result.cheapest.price == 1500
    assert result.origin == "YYZ"
    assert result.destination == "NRT"
    assert result.depart_date == DEPART
    collector._upsert_cheapest.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_single_date_picks_cheapest_across_providers() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    p1 = make_provider("serpapi", [make_result(1800, provider="serpapi")])
    p2 = make_provider("serpapi_b", [make_result(1200, provider="serpapi_b")])
    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[p1, p2],
    )
    collector._upsert_cheapest = AsyncMock()

    result = await collector.collect_single_date("YYZ", "NRT", DEPART, ROUTE_ID)

    assert result.cheapest is not None
    assert result.cheapest.price == 1200
    assert result.cheapest.provider == "serpapi_b"


@pytest.mark.asyncio
async def test_collect_single_date_one_provider_fails() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    p_good = make_provider("serpapi", [make_result(1500)])
    p_bad = MagicMock()
    p_bad.name = "serpapi_b"
    p_bad.search_one_way = AsyncMock(side_effect=RuntimeError("API down"))

    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[p_good, p_bad],
    )
    collector._upsert_cheapest = AsyncMock()
    collector._save_all_results = AsyncMock()

    result = await collector.collect_single_date("YYZ", "NRT", DEPART, ROUTE_ID)

    # Good provider's result still saved
    assert result.cheapest is not None
    assert result.cheapest.price == 1500
    # Error recorded
    assert "serpapi_b" in result.errors
    # Both a success log and an error log were added
    assert session.add.call_count == 2


@pytest.mark.asyncio
async def test_collect_single_date_reports_provider_health_callbacks() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    p_good = make_provider("searchapi", [make_result(1500, provider="searchapi")])
    p_bad = MagicMock()
    p_bad.name = "searchapi_b"
    p_bad.search_one_way = AsyncMock(side_effect=RuntimeError("API down"))

    success_cb = MagicMock()
    failure_cb = MagicMock()

    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[p_good, p_bad],
        on_provider_success=success_cb,
        on_provider_failure=failure_cb,
    )
    collector._upsert_cheapest = AsyncMock()
    collector._save_all_results = AsyncMock()

    await collector.collect_single_date("YYZ", "NRT", DEPART, ROUTE_ID)

    success_cb.assert_called_once_with("searchapi")
    failure_cb.assert_called_once()
    assert failure_cb.call_args.args[0] == "searchapi_b"


@pytest.mark.asyncio
async def test_collect_single_date_no_results() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    provider = make_provider("kiwi", [])
    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[provider],
    )
    collector._upsert_cheapest = AsyncMock()

    result = await collector.collect_single_date("YYZ", "NRT", DEPART, ROUTE_ID)

    assert result.cheapest is None
    collector._upsert_cheapest.assert_not_awaited()


@pytest.mark.asyncio
async def test_collect_route_batch_stats() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    provider = make_provider("serpapi", [make_result(1500)])
    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[provider],
    )
    collector._upsert_cheapest = AsyncMock()

    dates = [DEPART + timedelta(days=i) for i in range(3)]
    stats = await collector.collect_route_batch(
        origin="YYZ",
        destinations=["NRT"],
        dates=dates,
        route_group_id=ROUTE_ID,
        batch_size=3,
        delay_seconds=0,
    )

    assert stats["success"] == 3
    assert stats["errors"] == 0


# ── upsert logic test (verifies SQL param assembly) ──────────────────────────

@pytest.mark.asyncio
async def test_upsert_cheapest_sends_correct_params() -> None:
    session = AsyncMock()
    session.execute = AsyncMock()

    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[],
    )
    result = make_result(1250, airline="AC", provider="serpapi")
    result.deep_link = "https://example.com/booking"

    await collector._upsert_cheapest(
        session=session,
        route_group_id=ROUTE_ID,
        origin="YYZ",
        destination="NRT",
        depart_date=DEPART,
        result=result,
    )

    session.execute.assert_awaited_once()
    call_args = session.execute.call_args[0]
    params = call_args[1]
    assert params["origin"] == "YYZ"
    assert params["destination"] == "NRT"
    assert params["price"] == 1250
    assert params["provider"] == "serpapi"
    # Bare IATA code is expanded to the human-readable name on persistence.
    assert params["airline"] == "Air Canada"


@pytest.mark.asyncio
async def test_round_trip_calls_search_round_trip_with_return_date() -> None:
    """Regression: a route group with trip_type='round_trip' must trigger the
    provider's round-trip search using depart + nights, not silently fall
    through to one_way."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    provider = MagicMock()
    provider.name = "searchapi"
    provider.search_one_way = AsyncMock(return_value=[])
    provider.search_round_trip = AsyncMock(
        return_value=[make_result(2400, provider="searchapi")]
    )

    collector = PriceCollector(
        session_factory=make_session_factory(session),
        providers=[provider],
    )
    collector._upsert_cheapest = AsyncMock()
    collector._save_all_results = AsyncMock()

    result = await collector.collect_single_date(
        origin="YYZ",
        destination="NRT",
        depart_date=DEPART,
        route_group_id=ROUTE_ID,
        trip_type="round_trip",
        nights=10,
    )

    provider.search_round_trip.assert_awaited_once()
    provider.search_one_way.assert_not_awaited()
    kwargs = provider.search_round_trip.call_args.kwargs
    assert kwargs["depart_date"] == DEPART
    assert kwargs["return_date"] == DEPART + timedelta(days=10)
    assert result.cheapest is not None
    assert result.cheapest.price == 2400
