from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_run import CollectionRun
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.route_group import RouteGroup
from app.models.scrape_log import ScrapeLog
from app.models.user import User
from app.providers.registry import ProviderRegistry
from app.schemas.stats import OverviewStats, ProviderStat


async def get_overview(
    session: AsyncSession,
    registry: ProviderRegistry,
    current_user: User,
) -> OverviewStats:
    groups_query = select(func.count()).where(RouteGroup.is_active.is_(True))
    active_groups = (await session.execute(groups_query)).scalar_one() or 0

    price_query = select(func.count(DailyCheapestPrice.id)).join(
        RouteGroup,
        RouteGroup.id == DailyCheapestPrice.route_group_id,
    )
    total_prices = (await session.execute(price_query)).scalar_one() or 0

    origins_query = select(func.count(DailyCheapestPrice.origin.distinct())).join(
        RouteGroup,
        RouteGroup.id == DailyCheapestPrice.route_group_id,
    )
    total_origins = (await session.execute(origins_query)).scalar_one() or 0

    destinations_query = select(func.count(DailyCheapestPrice.destination.distinct())).join(
        RouteGroup,
        RouteGroup.id == DailyCheapestPrice.route_group_id,
    )
    total_destinations = (await session.execute(destinations_query)).scalar_one() or 0

    last_collection_at = None
    last_collection_status = None
    last_run = (
        await session.execute(select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    if last_run:
        last_collection_at = last_run.started_at
        last_collection_status = last_run.status

    provider_status = registry.status()
    provider_stats: dict[str, ProviderStat] = {}

    for name, provider_state in provider_status.items():
        configured = provider_state in {"configured", "active"}
        last_success = None
        success_rate = None

        if configured:
            last_success_query = select(func.max(ScrapeLog.created_at)).where(
                ScrapeLog.provider == name,
                ScrapeLog.status == "success",
            )
            total_logs_query = select(func.count()).where(ScrapeLog.provider == name)
            success_logs_query = select(func.count()).where(
                ScrapeLog.provider == name,
                ScrapeLog.status == "success",
            )

            last_success = (await session.execute(last_success_query)).scalar_one()
            total_logs = (await session.execute(total_logs_query)).scalar_one() or 0
            if total_logs > 0:
                success_count = (await session.execute(success_logs_query)).scalar_one() or 0
                success_rate = round(success_count / total_logs, 4)

        provider_stats[name] = ProviderStat(
            configured=configured,
            last_success=last_success,
            success_rate=success_rate,
        )

    return OverviewStats(
        active_route_groups=active_groups,
        total_prices_collected=total_prices,
        total_origins=total_origins,
        total_destinations=total_destinations,
        last_collection_at=last_collection_at,
        last_collection_status=last_collection_status,
        provider_stats=provider_stats,
    )
