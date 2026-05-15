"""Tests for scheduler date generation with defensive bounds."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from app.tasks.scheduler import FlightScheduler


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


def make_group(
    days_ahead: int = 30,
    start_date: date | None = None,
    end_date: date | None = None,
) -> MagicMock:
    group = MagicMock()
    group.days_ahead = days_ahead
    group.start_date = start_date
    group.end_date = end_date
    return group


def test_group_dates_normal_range() -> None:
    scheduler = make_scheduler()
    group = make_group(days_ahead=7)
    dates = scheduler._group_dates(group)
    assert len(dates) == 8  # today + 7 days
    assert dates[0] == date.today()
    assert dates[-1] == date.today() + timedelta(days=7)


def test_group_dates_explicit_range() -> None:
    scheduler = make_scheduler()
    group = make_group(
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 5),
    )
    dates = scheduler._group_dates(group)
    assert len(dates) == 5
    assert dates[0] == date(2026, 6, 1)
    assert dates[-1] == date(2026, 6, 5)


def test_group_dates_capped_at_730() -> None:
    """Even if days_ahead is absurdly large, dates are capped at 730."""
    scheduler = make_scheduler()
    group = make_group(days_ahead=5000)
    dates = scheduler._group_dates(group)
    assert len(dates) == 730


def test_group_dates_explicit_end_capped_at_730() -> None:
    """An explicit end_date far in the future is still capped."""
    scheduler = make_scheduler()
    group = make_group(
        start_date=date(2026, 1, 1),
        end_date=date(2030, 1, 1),  # ~4 years
    )
    dates = scheduler._group_dates(group)
    assert len(dates) == 730


def test_group_dates_zero_days_ahead() -> None:
    scheduler = make_scheduler()
    group = make_group(days_ahead=0)
    dates = scheduler._group_dates(group)
    assert len(dates) == 1
    assert dates[0] == date.today()


def test_group_dates_one_day() -> None:
    scheduler = make_scheduler()
    group = make_group(days_ahead=1)
    dates = scheduler._group_dates(group)
    assert len(dates) == 2


def test_group_dates_clamps_past_start_to_today() -> None:
    scheduler = make_scheduler()
    group = make_group(
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() + timedelta(days=2),
    )
    dates = scheduler._group_dates(group)
    assert dates[0] == date.today()
    assert dates[-1] == date.today() + timedelta(days=2)


def test_group_dates_returns_empty_when_explicit_end_is_in_past() -> None:
    scheduler = make_scheduler()
    group = make_group(
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() - timedelta(days=1),
    )
    assert scheduler._group_dates(group) == []
