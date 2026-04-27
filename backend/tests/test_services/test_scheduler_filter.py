from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.scheduler import FlightScheduler

TODAY = date.today()
D1 = TODAY + timedelta(days=1)
D2 = TODAY + timedelta(days=2)
D3 = TODAY + timedelta(days=3)


def make_scheduler() -> FlightScheduler:
    settings = MagicMock()
    settings.scheduler_enabled = False
    settings.telegram_bot_token = ""
    settings.telegram_chat_id = ""
    settings.sentry_dsn = ""
    return FlightScheduler(
        settings=settings,
        session_factory=MagicMock(),
        provider_registry=MagicMock(),
    )


def make_execute_result(rows: list[tuple]) -> MagicMock:
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


ROUTE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_partial_destination_not_excluded() -> None:
    """Date with only 1 of 2 destinations collected must NOT be filtered out."""
    scheduler = make_scheduler()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=make_execute_result([(D1, 1)]))

    remaining = await scheduler._filter_already_scraped(
        session, ROUTE_ID, "YYZ", ["SGN", "HAN"], [D1, D2]
    )

    assert D1 in remaining
    assert D2 in remaining


@pytest.mark.asyncio
async def test_all_destinations_excludes_date() -> None:
    """Date with all destinations collected IS excluded."""
    scheduler = make_scheduler()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=make_execute_result([(D1, 2)]))

    remaining = await scheduler._filter_already_scraped(
        session, ROUTE_ID, "YYZ", ["SGN", "HAN"], [D1, D2]
    )

    assert D1 not in remaining
    assert D2 in remaining


@pytest.mark.asyncio
async def test_all_dates_fully_scraped_returns_empty() -> None:
    """If every date is fully collected, the returned list is empty."""
    scheduler = make_scheduler()
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=make_execute_result([(D1, 1), (D2, 1)])
    )

    remaining = await scheduler._filter_already_scraped(
        session, ROUTE_ID, "YYZ", ["SGN"], [D1, D2]
    )

    assert remaining == []


@pytest.mark.asyncio
async def test_no_scrapes_returns_all_dates() -> None:
    """If nothing was collected yet, all dates are returned unchanged."""
    scheduler = make_scheduler()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=make_execute_result([]))

    dates = [D1, D2, D3]
    remaining = await scheduler._filter_already_scraped(
        session, ROUTE_ID, "YYZ", ["SGN", "HAN"], dates
    )

    assert remaining == dates


@pytest.mark.asyncio
async def test_filter_is_scoped_to_route_group() -> None:
    scheduler = make_scheduler()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=make_execute_result([]))

    await scheduler._filter_already_scraped(
        session, ROUTE_ID, "YYZ", ["SGN", "HAN"], [D1, D2]
    )

    params = session.execute.await_args.args[1]
    assert params["route_group_id"] == ROUTE_ID


@pytest.mark.asyncio
async def test_trigger_single_group_forwards_trip_type_and_nights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: trigger_single_group must pass the route group's trip_type
    and nights into the collector, otherwise round-trip groups silently get
    scraped as one-way and the export shows wrong fares."""
    from uuid import uuid4

    from app.tasks import scheduler as scheduler_module

    scheduler = make_scheduler()
    scheduler.settings.scrape_batch_size = 4
    scheduler.settings.scrape_delay_seconds = 0.0

    group = MagicMock()
    group.id = uuid4()
    group.is_active = True
    group.origins = ["YYZ"]
    group.destinations = ["NRT"]
    group.currency = "USD"
    group.max_stops = None
    group.trip_type = "round_trip"
    group.nights = 14
    group.start_date = None
    group.end_date = None
    group.days_ahead = 7

    captured: dict = {}

    class DummyCollector:
        def __init__(self, *a, **kw) -> None:
            pass

        async def collect_route_batch(self, **kwargs):
            captured.update(kwargs)
            return {"success": 0, "errors": 0, "skipped": 0}

    monkeypatch.setattr(scheduler_module, "PriceCollector", DummyCollector)

    fake_provider = MagicMock()
    fake_provider.is_configured.return_value = True
    scheduler.provider_registry.get_enabled = MagicMock(return_value=[fake_provider])

    # Stub the DB lookup of the group and the freshness filter.
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = group
    session = AsyncMock()
    session.execute = AsyncMock(return_value=select_result)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(return_value=[D1])

    await scheduler.trigger_single_group(group.id)

    assert captured["trip_type"] == "round_trip"
    assert captured["nights"] == 14
    assert captured["currency"] == "USD"


@pytest.mark.asyncio
async def test_trigger_single_group_collects_multi_city_special_sheets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    from app.tasks import scheduler as scheduler_module

    scheduler = make_scheduler()
    scheduler.settings.scrape_batch_size = 4
    scheduler.settings.scrape_delay_seconds = 0.0

    group = MagicMock()
    group.id = uuid4()
    group.is_active = True
    group.origins = ["YYZ"]
    group.destinations = ["BER"]
    group.currency = "USD"
    group.max_stops = None
    group.trip_type = "multi_city"
    group.nights = 7
    group.start_date = None
    group.end_date = None
    group.days_ahead = 5
    group.special_sheets = [
        {
            "name": "Leg 2",
            "origin": "BER",
            "destination_label": "Tokyo",
            "destinations": ["NRT", "HND"],
            "columns": 4,
        }
    ]

    captured: list[dict] = []

    class DummyCollector:
        def __init__(self, *a, **kw) -> None:
            pass

        async def collect_route_batch(self, **kwargs):
            captured.append(kwargs)
            return {"success": 0, "errors": 0, "skipped": 0}

    monkeypatch.setattr(scheduler_module, "PriceCollector", DummyCollector)

    fake_provider = MagicMock()
    fake_provider.is_configured.return_value = True
    scheduler.provider_registry.get_enabled = MagicMock(return_value=[fake_provider])

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = group
    session = AsyncMock()
    session.execute = AsyncMock(return_value=select_result)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(side_effect=lambda **kwargs: kwargs["dates"])

    await scheduler.trigger_single_group(group.id)

    assert len(captured) == 2
    assert captured[0]["origin"] == "YYZ"
    assert captured[0]["destinations"] == ["BER"]
    assert captured[0]["trip_type"] == "multi_city"
    assert captured[1]["origin"] == "BER"
    assert captured[1]["destinations"] == ["NRT", "HND"]
    assert captured[1]["trip_type"] == "one_way"
    assert captured[1]["nights"] is None


@pytest.mark.asyncio
async def test_trigger_single_group_updates_live_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    from app.tasks import scheduler as scheduler_module

    scheduler = make_scheduler()
    scheduler.settings.scrape_batch_size = 4
    scheduler.settings.scrape_delay_seconds = 0.0

    group = MagicMock()
    group.id = uuid4()
    group.is_active = True
    group.origins = ["AMD"]
    group.destinations = ["YYZ"]
    group.currency = "USD"
    group.max_stops = None
    group.trip_type = "one_way"
    group.nights = 0
    group.start_date = None
    group.end_date = None
    group.days_ahead = 7

    class DummyCollector:
        def __init__(self, *a, **kw) -> None:
            self.on_item_progress = kw["on_item_progress"]

        async def collect_route_batch(self, **kwargs):
            self.on_item_progress("success", "YYZ", D1)
            self.on_item_progress("skipped", "YYZ", D2)
            return {"success": 1, "errors": 0, "skipped": 1}

    monkeypatch.setattr(scheduler_module, "PriceCollector", DummyCollector)

    fake_provider = MagicMock()
    fake_provider.is_configured.return_value = True
    scheduler.provider_registry.get_enabled = MagicMock(return_value=[fake_provider])

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = group
    session = AsyncMock()
    session.execute = AsyncMock(return_value=select_result)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(return_value=[D1, D2])

    stats = await scheduler.trigger_single_group(group.id)

    assert stats == {"success": 1, "errors": 0, "skipped": 1}
    assert scheduler.progress["routes_total"] == 1
    assert scheduler.progress["routes_done"] == 1
    assert scheduler.progress["prices_total"] == 2
    assert scheduler.progress["prices_done"] == 2
    assert scheduler.progress["dates_scraped"] == 1
    assert scheduler.progress["current_origin"] == "AMD"
    assert scheduler.progress["current_destination"] == "YYZ"
    assert scheduler.progress["current_date"] == D2.isoformat()
