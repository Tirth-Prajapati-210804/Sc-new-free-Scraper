from __future__ import annotations

from datetime import UTC, datetime
from datetime import date, timedelta
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redaction import redact_text
from app.models.collection_run import CollectionRun
from app.models.route_group import RouteGroup
from app.providers.registry import ProviderRegistry
from app.services.alert_service import AlertService
from app.services.price_collector import PriceCollector
from app.utils.route_segments import iter_group_segments

log = get_logger(__name__)


class FlightScheduler:
    """
    Goal B Final:
    - freshness scheduling
    - historical route scoring
    - smart collection ordering
    - lower quota waste
    """

    _MAX_DATES = 730

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        provider_registry: ProviderRegistry,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.provider_registry = provider_registry

        self.alert_service = AlertService(settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")

        self._is_running = False
        self._is_collecting = False
        self._stop_requested = False

        self._progress: dict = {
            "routes_total": 0,
            "routes_done": 0,
            "routes_failed": 0,
            "prices_total": 0,
            "prices_started": 0,
            "prices_done": 0,
            "prices_failed": 0,
            "dates_scraped": 0,
            "current_origin": "",
            "current_destination": "",
            "current_date": "",
        }

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._is_running and self.scheduler.running

    @property
    def is_collecting(self) -> bool:
        return self._is_collecting

    @property
    def progress(self) -> dict:
        return dict(self._progress)

    def _reset_progress(self) -> None:
        self._progress = {
            "routes_total": 0,
            "routes_done": 0,
            "routes_failed": 0,
            "prices_total": 0,
            "prices_started": 0,
            "prices_done": 0,
            "prices_failed": 0,
            "dates_scraped": 0,
            "current_origin": "",
            "current_destination": "",
            "current_date": "",
        }

    def _record_item_started(
        self,
        origin: str,
        destination: str,
        depart_date: date,
    ) -> None:
        self._progress["current_origin"] = origin
        self._progress["current_destination"] = destination
        self._progress["current_date"] = depart_date.isoformat()
        self._progress["prices_started"] += 1

    def _record_item_progress(
        self,
        status: str,
        origin: str,
        destination: str,
        depart_date: date,
    ) -> None:
        self._progress["current_origin"] = origin
        self._progress["current_destination"] = destination
        self._progress["current_date"] = depart_date.isoformat()

        if status == "stopped":
            return

        self._progress["prices_done"] += 1

        if status == "success":
            self._progress["dates_scraped"] += 1
        elif status == "error":
            self._progress["prices_failed"] += 1

    def request_stop(self) -> None:
        self._stop_requested = True

    # --------------------------------------------------
    # START
    # --------------------------------------------------

    def start(self) -> None:
        if not self.settings.scheduler_enabled:
            return

        self.scheduler.add_job(
            self.run_collection_cycle,
            trigger="interval",
            minutes=self.settings.scheduler_interval_minutes,
            id="flight_collection",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger="interval",
            hours=24,
            id="daily_cleanup",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True

        log.info(
            "scheduler_started",
            interval=self.settings.scheduler_interval_minutes,
        )

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

        self._is_running = False

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------

    async def run_collection_cycle(self) -> None:
        if self._is_collecting:
            return

        self._is_collecting = True
        self._stop_requested = False

        lock_acquired = False

        try:
            async with self.session_factory() as session:
                lock_acquired = await self._acquire_global_lock(session)
                if not lock_acquired:
                    return

                try:
                    run = CollectionRun(
                        status="running",
                        started_at=datetime.now(UTC),
                    )
                    session.add(run)
                    await session.flush()
                    await session.commit()

                    providers = self.provider_registry.get_enabled()

                    if not providers:
                        run.status = "failed"
                        run.errors = [
                            {
                                "code": "provider_unavailable",
                                "detail": "No enabled flight data provider is available for collection.",
                                "provider_status": self.provider_registry.status(),
                            }
                        ]
                        run.finished_at = func.now()
                        await session.commit()
                        return

                    groups_result = await session.execute(
                        select(RouteGroup).where(RouteGroup.is_active.is_(True))
                    )
                    groups = list(groups_result.scalars().all())

                    ranked_routes = []

                    for group in groups:
                        dates = self._group_dates(group)

                        for segment in iter_group_segments(group):
                            score = await self._route_score(
                                session=session,
                                group_id=group.id,
                                origin=segment.origin,
                            )

                            ranked_routes.append(
                                (
                                    score,
                                    group,
                                    segment,
                                    dates,
                                )
                            )

                    ranked_routes.sort(key=lambda x: x[0], reverse=True)

                    total_success = 0
                    total_errors = 0
                    planned_routes: list[tuple[RouteGroup, object, list[date]]] = []
                    self._reset_progress()

                    for _, group, segment, dates in ranked_routes:
                        if self._stop_requested:
                            break

                        remaining = await self._filter_already_scraped(
                            session=session,
                            route_group_id=group.id,
                            origin=segment.origin,
                            destinations=segment.destinations,
                            dates=dates,
                        )

                        if not remaining:
                            continue

                        planned_routes.append((group, segment, remaining))
                        self._progress["prices_total"] += len(remaining) * len(segment.destinations)

                    self._progress["routes_total"] = len(planned_routes)
                    run.routes_total = len(planned_routes)
                    await session.commit()

                    collector = PriceCollector(
                        session_factory=self.session_factory,
                        providers=providers,
                        on_provider_success=self.provider_registry.report_success,
                        on_provider_failure=self.provider_registry.report_failure,
                        on_item_started=lambda origin, destination, depart_date: self._record_item_started(
                            origin,
                            destination,
                            depart_date,
                        ),
                        on_item_progress=lambda status, origin, destination, depart_date: self._record_item_progress(
                            status,
                            origin,
                            destination,
                            depart_date,
                        ),
                    )

                    for group, segment, remaining in planned_routes:
                        if self._stop_requested:
                            break

                        self._progress["current_origin"] = segment.origin
                        self._progress["current_destination"] = ""
                        self._progress["current_date"] = ""
                        batch_size = 1 if segment.trip_type == "multi_city" else self.settings.scrape_batch_size

                        try:
                            stats = await collector.collect_route_batch(
                                origin=segment.origin,
                                destinations=segment.destinations,
                                dates=remaining,
                                route_group_id=group.id,
                                batch_size=batch_size,
                                delay_seconds=self.settings.scrape_delay_seconds,
                                stop_check=lambda: self._stop_requested,
                                currency=group.currency,
                                max_stops=group.max_stops,
                                trip_type=segment.trip_type,
                                nights=segment.nights,
                                return_origin=segment.return_origin,
                            )

                            total_success += stats["success"]
                            total_errors += stats["errors"]
                            self._progress["routes_done"] += 1

                        except Exception as exc:
                            total_errors += 1
                            self._progress["routes_done"] += 1
                            self._progress["routes_failed"] += 1

                            log.exception(
                                "route_failed",
                                origin=segment.origin,
                                error=redact_text(str(exc)),
                            )

                    if self._stop_requested:
                        run.status = "stopped"
                    elif total_success == 0 and total_errors > 0:
                        run.status = "failed"
                    else:
                        run.status = "completed"
                    run.routes_total = len(planned_routes)
                    run.routes_success = total_success
                    run.routes_failed = total_errors
                    run.dates_scraped = total_success
                    run.finished_at = datetime.now(UTC)
                    await session.commit()

                finally:
                    if lock_acquired:
                        try:
                            await self._release_global_lock(session)
                        except Exception:
                            pass

        finally:
            self._is_collecting = False
            self._stop_requested = False

    # --------------------------------------------------
    # HISTORICAL ROUTE SCORE
    # --------------------------------------------------

    async def _route_score(
        self,
        session,
        group_id,
        origin,
    ) -> float:

        result = await session.execute(
            text(
                """
                SELECT
                    COALESCE(MIN(price), 999999),
                    COUNT(*)
                FROM daily_cheapest_prices
                WHERE route_group_id = :gid
                  AND origin = :origin
                  AND depart_date >= current_date
                """
            ),
            {
                "gid": str(group_id),
                "origin": origin,
            },
        )

        row = result.first()

        min_price = float(row[0] or 999999)
        volume = int(row[1] or 0)

        price_score = max(0, 5000 - min_price)
        volume_score = min(volume * 5, 500)

        return price_score + volume_score

    # --------------------------------------------------
    # DATES
    # --------------------------------------------------

    def _group_dates(self, group: RouteGroup) -> list[date]:
        today = date.today()

        start = group.start_date or today
        end = group.end_date or (
            start + timedelta(
                days=min(group.days_ahead, self._MAX_DATES)
            )
        )

        total_days = min(
            (end - start).days + 1,
            self._MAX_DATES,
        )

        return [
            start + timedelta(days=i)
            for i in range(total_days)
        ]

    # --------------------------------------------------
    # COMPLETION FILTER
    # --------------------------------------------------

    async def _filter_already_scraped(
        self,
        session,
        route_group_id,
        origin,
        destinations,
        dates,
    ):
        """Return dates that still need work (not all destinations collected).

        One grouped query keeps this O(1) round-trips per group instead of
        O(dates), which mattered as days_ahead grew toward 365+.
        """

        if not dates or not destinations:
            return list(dates)

        # query. Under-scraping is the costly failure mode — extra scrapes are

        result = await session.execute(
            text(
                """
                SELECT depart_date, COUNT(DISTINCT destination)
                FROM daily_cheapest_prices
                WHERE route_group_id = :route_group_id
                AND origin = :origin
                AND destination = ANY(:destinations)
                AND depart_date = ANY(:dates)
                GROUP BY depart_date
                """
            ),
            {
                "route_group_id": str(route_group_id),
                "origin": origin,
                "destinations": list(destinations),
                "dates": list(dates),
            },
        )

        done_by_date = {row[0]: row[1] for row in result.fetchall()}
        target = len(destinations)

        return [d for d in dates if done_by_date.get(d, 0) < target]

    # --------------------------------------------------
    # LOCKS
    # --------------------------------------------------

    async def _acquire_global_lock(self, session) -> bool:
        result = await session.execute(
            text("SELECT pg_try_advisory_lock(987654321)")
        )
        return bool(result.scalar())

    async def _release_global_lock(self, session):
        await session.execute(
            text("SELECT pg_advisory_unlock(987654321)")
        )

    # --------------------------------------------------
    # MANUAL
    # --------------------------------------------------

    async def trigger_single_group(
        self,
        group_id: UUID,
        target_dates: list[date] | None = None,
    ) -> dict[str, int]:

        stats = {
            "success": 0,
            "errors": 0,
            "skipped": 0,
        }

        if self._is_collecting:
            return stats

        self._is_collecting = True
        self._stop_requested = False
        lock_acquired = False

        try:
            async with self.session_factory() as session:
                lock_acquired = await self._acquire_global_lock(session)
                if not lock_acquired:
                    return stats

                try:
                    run = CollectionRun(
                        status="running",
                        started_at=datetime.now(UTC),
                    )
                    session.add(run)
                    await session.flush()
                    await session.commit()

                    result = await session.execute(
                        select(RouteGroup).where(
                            RouteGroup.id == group_id,
                            RouteGroup.is_active.is_(True),
                        )
                    )

                    group = result.scalar_one_or_none()

                    if not group:
                        run.status = "failed"
                        run.errors = [{"code": "group_not_found", "detail": "Route group not found or inactive."}]
                        run.finished_at = datetime.now(UTC)
                        await session.commit()
                        return stats

                    providers = self.provider_registry.get_enabled()

                    if not providers:
                        run.status = "failed"
                        run.errors = [{"code": "provider_unavailable", "detail": "No enabled provider is available."}]
                        run.finished_at = datetime.now(UTC)
                        await session.commit()
                        return stats

                    dates = target_dates if target_dates else self._group_dates(group)
                    planned_segments: list[tuple[object, list[date]]] = []
                    self._reset_progress()

                    for segment in iter_group_segments(group):
                        remaining = await self._filter_already_scraped(
                            session=session,
                            route_group_id=group.id,
                            origin=segment.origin,
                            destinations=segment.destinations,
                            dates=dates,
                        )

                        if not remaining:
                            continue

                        planned_segments.append((segment, remaining))
                        self._progress["prices_total"] += len(remaining) * len(segment.destinations)

                    self._progress["routes_total"] = len(planned_segments)
                    run.routes_total = len(planned_segments)
                    await session.commit()

                    collector = PriceCollector(
                        session_factory=self.session_factory,
                        providers=providers,
                        on_provider_success=self.provider_registry.report_success,
                        on_provider_failure=self.provider_registry.report_failure,
                        on_item_started=lambda origin, destination, depart_date: self._record_item_started(
                            origin,
                            destination,
                            depart_date,
                        ),
                        on_item_progress=lambda status, origin, destination, depart_date: self._record_item_progress(
                            status,
                            origin,
                            destination,
                            depart_date,
                        ),
                    )

                    for segment, remaining in planned_segments:
                        if self._stop_requested:
                            break

                        self._progress["current_origin"] = segment.origin
                        self._progress["current_destination"] = ""
                        self._progress["current_date"] = ""
                        batch_size = 1 if segment.trip_type == "multi_city" else self.settings.scrape_batch_size

                        part = await collector.collect_route_batch(
                            origin=segment.origin,
                            destinations=segment.destinations,
                            dates=remaining,
                            route_group_id=group.id,
                            batch_size=batch_size,
                            delay_seconds=self.settings.scrape_delay_seconds,
                            stop_check=lambda: self._stop_requested,
                            currency=group.currency,
                            max_stops=group.max_stops,
                            trip_type=segment.trip_type,
                            nights=segment.nights,
                            return_origin=segment.return_origin,
                        )

                        stats["success"] += part["success"]
                        stats["errors"] += part["errors"]
                        stats["skipped"] += part["skipped"]
                        self._progress["routes_done"] += 1

                    if self._stop_requested:
                        run.status = "stopped"
                    elif stats["success"] == 0 and stats["errors"] > 0:
                        run.status = "failed"
                    else:
                        run.status = "completed"
                    run.routes_success = stats["success"]
                    run.routes_failed = stats["errors"]
                    run.dates_scraped = stats["success"]
                    run.finished_at = datetime.now(UTC)
                    await session.commit()

                finally:
                    if lock_acquired:
                        try:
                            await self._release_global_lock(session)
                        except Exception:
                            pass

        finally:
            self._is_collecting = False
            self._stop_requested = False

        return stats

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    async def cleanup_old_data(self) -> None:
        try:
            async with self.session_factory() as session:
                await session.execute(
                    text(
                        "DELETE FROM scrape_logs "
                        "WHERE created_at < now() - interval '30 days'"
                    )
                )

                await session.execute(
                    text(
                        "DELETE FROM collection_runs "
                        "WHERE started_at < now() - interval '30 days'"
                    )
                )

                await session.execute(
                    text(
                        "DELETE FROM all_flight_results "
                        "WHERE depart_date < current_date - 7"
                    )
                )

                await session.commit()

        except Exception as exc:
            log.exception(
                "cleanup_failed",
                error=redact_text(str(exc)),
            )
