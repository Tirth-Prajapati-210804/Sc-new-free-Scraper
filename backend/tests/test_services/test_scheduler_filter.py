from __future__ import annotations

import asyncio
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
    group.market = "ca"
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
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=select_result)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(return_value=[D1])

    await scheduler.trigger_single_group(group.id)

    assert captured["trip_type"] == "round_trip"
    assert captured["nights"] == 14
    assert captured["market"] == "ca"
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
    group.market = "ca"
    group.max_stops = None
    group.trip_type = "multi_city"
    group.nights = 7
    group.start_date = None
    group.end_date = None
    group.days_ahead = 5
    group.special_sheets = [
        {
            "name": "Return Leg",
            "origin": "BUD",
            "destination_label": "Toronto",
            "destinations": ["YYZ"],
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
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=select_result)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(side_effect=lambda **kwargs: kwargs["dates"])

    await scheduler.trigger_single_group(group.id)

    assert len(captured) == 1
    assert captured[0]["origin"] == "YYZ"
    assert captured[0]["destinations"] == ["BER"]
    assert captured[0]["trip_type"] == "multi_city"
    assert captured[0]["nights"] == 7
    assert captured[0]["market"] == "ca"
    assert captured[0]["return_origin"] == "BUD"
    assert captured[0]["batch_size"] == 2
    assert callable(captured[0]["stop_check"])


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
    group.market = "us"
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
            self.on_item_progress("success", "AMD", "YYZ", D1)
            self.on_item_progress("skipped", "AMD", "YYZ", D2)
            return {"success": 1, "errors": 0, "skipped": 1}

    monkeypatch.setattr(scheduler_module, "PriceCollector", DummyCollector)

    fake_provider = MagicMock()
    fake_provider.is_configured.return_value = True
    scheduler.provider_registry.get_enabled = MagicMock(return_value=[fake_provider])

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = group
    session = AsyncMock()
    session.add = MagicMock()
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


@pytest.mark.asyncio
async def test_trigger_single_group_clears_stale_errors_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    from app.tasks import scheduler as scheduler_module

    scheduler = make_scheduler()
    scheduler.settings.scrape_batch_size = 1
    scheduler.settings.scrape_delay_seconds = 0.0

    group = MagicMock()
    group.id = uuid4()
    group.is_active = True
    group.origins = ["YVR"]
    group.destinations = ["DPS"]
    group.currency = "USD"
    group.market = "ca"
    group.max_stops = 1
    group.trip_type = "multi_city"
    group.nights = 12
    group.start_date = None
    group.end_date = None
    group.days_ahead = 30
    group.special_sheets = [
        {
            "name": "SIN-YVR",
            "origin": "SIN",
            "destination_label": "YVR",
            "destinations": ["YVR"],
            "columns": 4,
        }
    ]

    class DummyCollector:
        def __init__(self, *a, **kw) -> None:
            pass

        async def collect_route_batch(self, **kwargs):
            return {"success": 1, "errors": 0, "skipped": 0}

    monkeypatch.setattr(scheduler_module, "PriceCollector", DummyCollector)

    fake_provider = MagicMock()
    fake_provider.is_configured.return_value = True
    scheduler.provider_registry.get_enabled = MagicMock(return_value=[fake_provider])

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = group
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=select_result)

    captured_runs: list = []

    def capture_add(model) -> None:
        if model.__class__.__name__ == "CollectionRun":
            model.errors = ["Server restarted mid-collection"]
            captured_runs.append(model)

    session.add.side_effect = capture_add

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    scheduler.session_factory = factory

    scheduler._filter_already_scraped = AsyncMock(return_value=[D1])

    await scheduler.trigger_single_group(group.id)

    assert captured_runs
    assert captured_runs[0].status == "completed"
    assert captured_runs[0].errors == []


@pytest.mark.asyncio
async def test_scheduler_uses_dedicated_connection_for_advisory_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tasks import scheduler as scheduler_module

    scheduler = make_scheduler()

    connection = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar.return_value = True
    connection.execute = AsyncMock(return_value=execute_result)
    connection.close = AsyncMock()

    bind = MagicMock()
    bind.connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(scheduler_module, "AsyncEngine", MagicMock)
    scheduler.session_factory = MagicMock(kw={"bind": bind})

    session = AsyncMock()

    acquired = await scheduler._acquire_global_lock(session)

    assert acquired is True
    assert scheduler._lock_connection is connection
    session.execute.assert_not_called()

    await scheduler._release_global_lock(session)

    connection.execute.assert_awaited()
    connection.close.assert_awaited()
    assert scheduler._lock_connection is None


@pytest.mark.asyncio
async def test_start_collection_task_tracks_one_active_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = make_scheduler()
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_collection_cycle() -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(scheduler, "run_collection_cycle", fake_run_collection_cycle)

    assert scheduler.start_collection_task() is True
    await started.wait()
    assert scheduler._active_task is not None
    assert scheduler.start_collection_task() is False

    release.set()
    await scheduler._active_task
    assert scheduler._active_task is None


@pytest.mark.asyncio
async def test_start_single_group_task_tracks_one_active_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    scheduler = make_scheduler()
    group_id = uuid4()
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_trigger_single_group(
        passed_group_id,
        target_dates=None,
    ) -> dict[str, int]:
        assert passed_group_id == group_id
        assert target_dates == [D1]
        started.set()
        await release.wait()
        return {"success": 0, "errors": 0, "skipped": 0}

    monkeypatch.setattr(scheduler, "trigger_single_group", fake_trigger_single_group)

    assert scheduler.start_single_group_task(group_id, [D1]) is True
    await started.wait()
    assert scheduler._active_task is not None
    assert scheduler.start_single_group_task(group_id, [D1]) is False

    release.set()
    await scheduler._active_task
    assert scheduler._active_task is None
