from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_cheapest import DailyCheapestPrice
from app.models.route_group import RouteGroup
from app.models.scrape_log import ScrapeLog
from app.schemas.route_group import (
    PerOriginProgress,
    RouteGroupCreate,
    RouteGroupProgress,
    RouteGroupUpdate,
    ScrapeHealth,
)
from app.utils.route_segments import iter_group_segments

_NON_ERROR_STATUSES = {"success", "no_results"}
_ERROR_PRIORITY = ("quota_exhausted", "auth_error", "rate_limited", "error")


async def list_all(
    session: AsyncSession,
    active_only: bool = True,
    requesting_user_id: uuid.UUID | None = None,
    is_admin: bool = True,
) -> list[RouteGroup]:
    q = select(RouteGroup)
    if active_only:
        q = q.where(RouteGroup.is_active.is_(True))
    if not is_admin and requesting_user_id is not None:
        q = q.where(RouteGroup.user_id == requesting_user_id)
    result = await session.execute(q.order_by(RouteGroup.name))
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession,
    group_id: uuid.UUID,
    requesting_user_id: uuid.UUID | None = None,
    is_admin: bool = True,
) -> RouteGroup | None:
    q = select(RouteGroup).where(RouteGroup.id == group_id)
    if not is_admin and requesting_user_id is not None:
        q = q.where(RouteGroup.user_id == requesting_user_id)
    result = await session.execute(q)
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    data: RouteGroupCreate,
    owner_id: uuid.UUID | None = None,
) -> RouteGroup:
    group = RouteGroup(
        name=data.name,
        destination_label=data.destination_label,
        destinations=data.destinations,
        origins=data.origins,
        nights=data.nights,
        days_ahead=data.days_ahead,
        trip_type=data.trip_type,
        sheet_name_map=data.sheet_name_map or {o: o for o in data.origins},
        special_sheets=[s.model_dump() if hasattr(s, "model_dump") else s for s in (data.special_sheets or [])],
        currency=data.currency,
        max_stops=data.max_stops,
        start_date=data.start_date,
        end_date=data.end_date,
        user_id=owner_id,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def update(
    session: AsyncSession,
    group_id: uuid.UUID,
    data: RouteGroupUpdate,
    requesting_user_id: uuid.UUID | None = None,
    is_admin: bool = True,
) -> RouteGroup | None:
    group = await get_by_id(session, group_id, requesting_user_id=requesting_user_id, is_admin=is_admin)
    if not group:
        return None

    for field, value in data.model_dump(exclude_none=True).items():
        if field == "special_sheets" and value is not None:
            value = [s if isinstance(s, dict) else s.model_dump() for s in value]
        setattr(group, field, value)

    await session.commit()
    await session.refresh(group)
    return group


async def delete(
    session: AsyncSession,
    group_id: uuid.UUID,
    requesting_user_id: uuid.UUID | None = None,
    is_admin: bool = True,
) -> bool:
    # Verify access first
    group = await get_by_id(session, group_id, requesting_user_id=requesting_user_id, is_admin=is_admin)
    if not group:
        return False

    from sqlalchemy import delete as sa_delete
    from app.models.all_flight_result import AllFlightResult
    from app.models.daily_cheapest import DailyCheapestPrice

    # 1. Explicitly delete related flight data (redundant if CASCADE is set, but safer)
    await session.execute(sa_delete(DailyCheapestPrice).where(DailyCheapestPrice.route_group_id == group_id))
    await session.execute(sa_delete(AllFlightResult).where(AllFlightResult.route_group_id == group_id))

    # 2. Delete the group itself using a direct statement
    await session.execute(sa_delete(RouteGroup).where(RouteGroup.id == group_id))
    
    await session.commit()
    return True


async def get_progress(session: AsyncSession, group_id: uuid.UUID) -> RouteGroupProgress | None:
    # get_progress is called after access has already been verified by the router
    group = await get_by_id(session, group_id)
    if not group:
        return None

    dates = _group_dates(group)
    segments = iter_group_segments(group)
    total_dates = sum(len(segment.destinations) * len(dates) for segment in segments)

    # Total collected
    count_result = await session.execute(
        select(func.count()).where(DailyCheapestPrice.route_group_id == group_id)
    )
    dates_with_data = count_result.scalar_one() or 0

    # Last scraped
    last_result = await session.execute(
        select(func.max(DailyCheapestPrice.scraped_at)).where(
            DailyCheapestPrice.route_group_id == group_id
        )
    )
    last_scraped_at = last_result.scalar_one()

    # Per-origin breakdown
    per_origin: dict[str, PerOriginProgress] = {}
    expected_by_origin: dict[str, int] = {}
    for segment in segments:
        expected_by_origin[segment.origin] = expected_by_origin.get(segment.origin, 0) + (
            len(segment.destinations) * len(dates)
        )

    for origin, expected in expected_by_origin.items():
        collected_result = await session.execute(
            select(func.count()).where(
                DailyCheapestPrice.route_group_id == group_id,
                DailyCheapestPrice.origin == origin,
            )
        )
        collected = collected_result.scalar_one() or 0
        per_origin[origin] = PerOriginProgress(total=expected, collected=collected)

    coverage = (dates_with_data / total_dates * 100.0) if total_dates > 0 else 0.0

    dates_result = await session.execute(
        select(DailyCheapestPrice.depart_date)
        .where(DailyCheapestPrice.route_group_id == group_id)
        .distinct()
        .order_by(DailyCheapestPrice.depart_date)
    )
    scraped_dates = [d.isoformat() for (d,) in dates_result.fetchall()]

    health = await _compute_scrape_health(session, group_id, has_any_data=dates_with_data > 0)

    return RouteGroupProgress(
        route_group_id=group_id,
        name=group.name,
        total_dates=total_dates,
        dates_with_data=dates_with_data,
        coverage_percent=round(coverage, 2),
        last_scraped_at=last_scraped_at,
        per_origin=per_origin,
        scraped_dates=scraped_dates,
        health=health,
    )


def _group_dates(group: RouteGroup) -> list[date]:
    today = date.today()

    start = group.start_date or today
    end = group.end_date or (start + timedelta(days=min(group.days_ahead, 730)))
    total_days = min((end - start).days + 1, 730)

    return [start + timedelta(days=i) for i in range(total_days)]


async def _compute_scrape_health(
    session: AsyncSession,
    group_id: uuid.UUID,
    has_any_data: bool,
) -> ScrapeHealth:
    """Summarise the last hour of scrape activity into a single health object."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)

    last_attempt = (
        await session.execute(
            select(ScrapeLog.created_at, ScrapeLog.status, ScrapeLog.error_message)
            .where(ScrapeLog.route_group_id == group_id)
            .order_by(ScrapeLog.created_at.desc())
            .limit(1)
        )
    ).first()

    if last_attempt is None and not has_any_data:
        return ScrapeHealth(status="never_scraped")

    last_success_at = (
        await session.execute(
            select(func.max(ScrapeLog.created_at)).where(
                ScrapeLog.route_group_id == group_id,
                ScrapeLog.status.in_(list(_NON_ERROR_STATUSES)),
            )
        )
    ).scalar_one()

    counts_rows = (
        await session.execute(
            select(ScrapeLog.status, func.count())
            .where(
                ScrapeLog.route_group_id == group_id,
                ScrapeLog.created_at >= window_start,
            )
            .group_by(ScrapeLog.status)
        )
    ).all()
    counts = {status: count for status, count in counts_rows}
    successes = sum(c for s, c in counts.items() if s in _NON_ERROR_STATUSES)
    errors = sum(c for s, c in counts.items() if s not in _NON_ERROR_STATUSES)

    if last_attempt is None:
        return ScrapeHealth(
            status="ok",
            last_success_at=last_success_at,
            successes_last_hour=successes,
            errors_last_hour=errors,
        )

    last_attempt_at, last_status, last_error_message = last_attempt

    # Prefer the worst recent error class; otherwise "ok".
    recent_error_status = next(
        (s for s in _ERROR_PRIORITY if counts.get(s, 0) > 0),
        None,
    )
    if recent_error_status and successes == 0:
        status = recent_error_status
    elif last_status not in _NON_ERROR_STATUSES and successes == 0:
        status = last_status if last_status in _ERROR_PRIORITY else "error"
    else:
        status = "ok"

    return ScrapeHealth(
        status=status,
        last_attempt_at=last_attempt_at,
        last_success_at=last_success_at,
        last_error_message=last_error_message if status != "ok" else None,
        successes_last_hour=successes,
        errors_last_hour=errors,
    )
