from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.core.redaction import redact_text
from app.models.all_flight_result import AllFlightResult
from app.models.scrape_log import ScrapeLog
from app.providers.base import (
    FlightProvider,
    ProviderAuthError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitedError,
    ProviderResult,
)
from app.utils.airline_codes import normalize_airline

log = get_logger(__name__)


def _derive_return_date(depart_date: date, nights: int) -> date:
    """
    Return on the morning *after* the Nth night.
    Depart Apr 1 + 12 nights = Apr 13 (slept 12 nights, fly home on the 13th).
    """
    return depart_date + timedelta(days=max(1, nights))


def _classify_exception(exc: BaseException) -> str:
    if isinstance(exc, ProviderQuotaExhaustedError):
        return "quota_exhausted"
    if isinstance(exc, ProviderAuthError):
        return "auth_error"
    if isinstance(exc, ProviderRateLimitedError):
        return "rate_limited"
    message = str(exc).lower()
    if "invalid json" in message or "parse" in message:
        return "parse_error"
    return "provider_error"


@dataclass
class CollectionResult:
    origin: str
    destination: str
    depart_date: date
    cheapest: ProviderResult | None
    return_date: date | None = None
    stop_label: str | None = None
    provider_results: dict[str, list[ProviderResult]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class PriceCollector:
    """
    Goal B v2:
    - smart date priority
    - dead route cooldown
    - lower quota waste
    - faster useful coverage
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        providers: list[FlightProvider],
        on_provider_success: Callable[[str], None] | None = None,
        on_provider_failure: Callable[[str, BaseException], None] | None = None,
        on_item_started: Callable[[str, str, date], None] | None = None,
        on_item_progress: Callable[[str, str, str, date], None] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers
        self.on_provider_success = on_provider_success
        self.on_provider_failure = on_provider_failure
        self.on_item_started = on_item_started
        self.on_item_progress = on_item_progress

        self._route_failures: dict[str, int] = {}
        self._route_cooldown: dict[str, int] = {}

    # --------------------------------------------------
    # DATE PRIORITY
    # --------------------------------------------------

    def _score_date(self, d: date) -> tuple[int, int]:
        today = date.today()
        days_out = (d - today).days

        weekend_bonus = 0 if d.weekday() in (4, 5, 6) else 20
        near_bonus = min(max(days_out, 0), 365)

        return (near_bonus + weekend_bonus, days_out)

    def _prioritize_dates(self, dates: list[date]) -> list[date]:
        return sorted(set(dates), key=self._score_date)

    # --------------------------------------------------
    # ROUTE HEALTH
    # --------------------------------------------------

    def _route_key(
        self,
        origin: str,
        destination: str,
    ) -> str:
        return f"{origin}:{destination}"

    def _is_route_cooled(self, key: str) -> bool:
        remaining = self._route_cooldown.get(key, 0)

        if remaining <= 0:
            return False

        self._route_cooldown[key] = remaining - 1
        return True

    def _mark_route_success(self, key: str):
        self._route_failures[key] = 0
        self._route_cooldown.pop(key, None)

    def _mark_route_failure(self, key: str):
        fails = self._route_failures.get(key, 0) + 1
        self._route_failures[key] = fails

        # cooldown after repeated waste
        if fails >= 3:
            self._route_cooldown[key] = min(fails * 2, 12)

    def _provider_search_kwargs(
        self,
        provider: FlightProvider,
        *,
        market: str | None,
    ) -> dict[str, str]:
        if market and getattr(provider, "name", "") == "scrapingbee":
            return {"market": market}
        return {}

    # --------------------------------------------------
    # SINGLE SEARCH
    # --------------------------------------------------

    async def collect_single_date(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        route_group_id: UUID | None,
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
        trip_type: str = "one_way",
        nights: int | None = None,
        return_origin: str | None = None,
    ) -> CollectionResult:

        all_results: list[ProviderResult] = []
        provider_results: dict[str, list[ProviderResult]] = {}  
        errors: dict[str, str] = {}
        return_date: date | None = None

        async with self.session_factory() as session:
            for provider in self.providers:
                start = time.monotonic()

                try:
                    if trip_type == "multi_city":
                        stay_nights = nights or 1
                        if not return_origin:
                            raise RuntimeError("multi_city collection requires a return origin.")

                        return_date = _derive_return_date(depart_date, stay_nights)
                        results, stop_label = await self._search_multi_city_with_fallback(
                            provider=provider,
                            origin=origin,
                            destination=destination,
                            depart_date=depart_date,
                            return_origin=return_origin,
                            return_date=return_date,
                            currency=currency,
                            market=market,
                        )

                    elif trip_type == "round_trip":
                        stay_nights = nights or 3
                        return_date = _derive_return_date(depart_date, stay_nights)
                        if max_stops == 3:
                            results, stop_label = await self._search_round_trip_with_fallback(
                                provider=provider,
                                origin=origin,
                                destination=destination,
                                depart_date=depart_date,
                                return_date=return_date,
                                currency=currency,
                                market=market,
                            )
                        else:
                            results = await provider.search_round_trip(
                                origin=origin,
                                destination=destination,
                                depart_date=depart_date,
                                return_date=return_date,
                                currency=currency,
                                max_stops=max_stops,
                                **self._provider_search_kwargs(provider, market=market),
                            )
                            stop_label = None

                    else:
                        return_date = None
                        if max_stops == 3:
                            results, stop_label = await self._search_one_way_with_fallback(
                                provider=provider,
                                origin=origin,
                                destination=destination,
                                depart_date=depart_date,
                                currency=currency,
                                market=market,
                            )
                        else:
                            results = await provider.search_one_way(
                                origin=origin,
                                destination=destination,
                                depart_date=depart_date,
                                currency=currency,
                                max_stops=max_stops,
                                **self._provider_search_kwargs(provider, market=market),
                            )
                            stop_label = None

                    elapsed_ms = int((time.monotonic() - start) * 1000)

                    provider_results[provider.name] = results
                    all_results.extend(results)
                    if self.on_provider_success:
                        self.on_provider_success(provider.name)

                    session.add(
                        ScrapeLog(
                            route_group_id=route_group_id,
                            origin=origin,
                            destination=destination,
                            depart_date=depart_date,
                            provider=provider.name,
                            status="success" if results else "no_results",
                            offers_found=len(results),
                            cheapest_price=min(results, key=lambda r: r.price).price if results else None,
                            duration_ms=elapsed_ms,
                        )
                    )

                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    safe_error = redact_text(str(exc))
                    status = _classify_exception(exc)

                    errors[provider.name] = safe_error
                    if self.on_provider_failure:
                        self.on_provider_failure(provider.name, exc)

                    session.add(
                        ScrapeLog(
                            route_group_id=route_group_id,
                            origin=origin,
                            destination=destination,
                            depart_date=depart_date,
                            provider=provider.name,
                            status=status,
                            offers_found=0,
                            error_message=safe_error[:500],
                            duration_ms=elapsed_ms,
                        )
                    )

            cheapest = (
                min(all_results, key=lambda r: r.price)
                if all_results else None
            )

            if cheapest:
                await self._upsert_cheapest(
                    session,
                    route_group_id,
                    origin,
                    destination,
                    depart_date,
                    cheapest,
                )

                await self._save_all_results(
                    session,
                    route_group_id,
                    origin,
                    destination,
                    depart_date,
                    all_results,
                )

            await session.commit()

        return CollectionResult(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            cheapest=cheapest,
            return_date=return_date if trip_type == "multi_city" else None,
            stop_label=(
                str(cheapest.raw_data.get("stop_result_label"))
                if cheapest and isinstance(cheapest.raw_data, dict)
                else None
            ),
            provider_results=provider_results,
            errors=errors,
        )

    # --------------------------------------------------
    # MAIN BATCH
    # --------------------------------------------------

    async def collect_route_batch(
        self,
        origin: str,
        destinations: list[str],
        dates: list[date],
        route_group_id: UUID,
        batch_size: int = 4,
        delay_seconds: float = 1.2,
        stop_check: Callable[[], bool] | None = None,
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
        trip_type: str = "one_way",
        nights: int | None = None,
        return_origin: str | None = None,
    ) -> dict[str, int]:

        stats = {
            "success": 0,
            "errors": 0,
            "skipped": 0,
        }

        prioritized_dates = self._prioritize_dates(dates)
        semaphore = asyncio.Semaphore(batch_size)

        async def await_with_stop(coro):
            task = asyncio.create_task(coro)
            try:
                while not task.done():
                    if stop_check and stop_check():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        return None, True
                    await asyncio.sleep(0.25)
                return await task, False
            finally:
                if not task.done():
                    task.cancel()

        async def run_one(dest: str, depart_date: date):
            route_key = self._route_key(origin, dest)

            if self.on_item_started:
                self.on_item_started(origin, dest, depart_date)

            if self._is_route_cooled(route_key):
                if self.on_item_progress:
                    self.on_item_progress("skipped", origin, dest, depart_date)
                return "skipped"

            if stop_check and stop_check():
                return "stopped"

            async with semaphore:
                if stop_check and stop_check():
                    return "stopped"

                try:
                    result, was_stopped = await await_with_stop(
                        self.collect_single_date(
                            origin=origin,
                            destination=dest,
                            depart_date=depart_date,
                            route_group_id=route_group_id,
                            market=market,
                            currency=currency,
                            max_stops=max_stops,
                            trip_type=trip_type,
                            nights=nights,
                            return_origin=return_origin,
                        )
                    )
                    if was_stopped or result is None:
                        return "stopped"

                    if result.cheapest:
                        self._mark_route_success(route_key)
                        if self.on_item_progress:
                            self.on_item_progress("success", origin, dest, depart_date)
                        return "success"

                    self._mark_route_failure(route_key)
                    if self.on_item_progress:
                        self.on_item_progress("skipped", origin, dest, depart_date)
                    return "skipped"

                except Exception as exc:
                    self._mark_route_failure(route_key)

                    log.warning(
                        "collect_single_failed",
                        origin=origin,
                        destination=dest,
                        date=str(depart_date),
                        error=redact_text(str(exc)),
                    )

                    if self.on_item_progress:
                        self.on_item_progress("error", origin, dest, depart_date)
                    return "error"

        tasks = []

        for depart_date in prioritized_dates:
            for dest in destinations:
                tasks.append(run_one(dest, depart_date))

        for i in range(0, len(tasks), batch_size):
            if stop_check and stop_check():
                break

            chunk = tasks[i:i + batch_size]

            results = await asyncio.gather(
                *chunk,
                return_exceptions=True,
            )

            for r in results:
                if r == "success":
                    stats["success"] += 1
                elif r in {"skipped", "stopped"}:
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1

            if i + batch_size < len(tasks):
                slept = 0.0
                while slept < delay_seconds:
                    if stop_check and stop_check():
                        break
                    interval = min(0.25, delay_seconds - slept)
                    await asyncio.sleep(interval)
                    slept += interval

        return stats

    async def _search_multi_city_with_fallback(
        self,
        provider: FlightProvider,
        origin: str,
        destination: str,
        depart_date: date,
        return_origin: str,
        return_date: date,
        currency: str,
        market: str | None = None,
    ) -> tuple[list[ProviderResult], str | None]:
        fallback_order = (
            (1, "1 stop"),
            (2, "2 stop (1 stop unavailable)"),
            (0, "Direct (1 stop and 2 stop unavailable)"),
        )

        for max_stops, default_label in fallback_order:
            results = await provider.search_multi_city(
                legs=[
                    {
                        "departure_id": origin,
                        "arrival_id": destination,
                        "outbound_date": depart_date,
                    },
                    {
                        "departure_id": return_origin,
                        "arrival_id": origin,
                        "outbound_date": return_date,
                    },
                ],
                currency=currency,
                max_stops=max_stops,
                **self._provider_search_kwargs(provider, market=market),
            )

            if results:
                for result in results:
                    if not isinstance(result.raw_data, dict):
                        result.raw_data = {}
                    result.raw_data.setdefault("trip_type", "multi_city")
                    result.raw_data.setdefault("return_origin", return_origin)
                    result.raw_data.setdefault("return_destination", origin)
                    result.raw_data.setdefault("return_date", return_date.isoformat())
                    result.raw_data.setdefault("stop_result_label", default_label)
                return results, str(results[0].raw_data.get("stop_result_label") or default_label)

        return [], None

    async def _search_one_way_with_fallback(
        self,
        provider: FlightProvider,
        origin: str,
        destination: str,
        depart_date: date,
        currency: str,
        market: str | None = None,
    ) -> tuple[list[ProviderResult], str | None]:
        fallback_order = (
            (1, "1 stop"),
            (2, "2 stop (1 stop unavailable)"),
            (0, "Direct (1 stop and 2 stop unavailable)"),
        )
        for max_stops, default_label in fallback_order:
            results = await provider.search_one_way(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                currency=currency,
                max_stops=max_stops,
                **self._provider_search_kwargs(provider, market=market),
            )
            if results:
                for result in results:
                    if not isinstance(result.raw_data, dict):
                        result.raw_data = {}
                    result.raw_data.setdefault("stop_result_label", default_label)
                return results, str(results[0].raw_data.get("stop_result_label") or default_label)
        return [], None

    async def _search_round_trip_with_fallback(
        self,
        provider: FlightProvider,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        currency: str,
        market: str | None = None,
    ) -> tuple[list[ProviderResult], str | None]:
        fallback_order = (
            (1, "1 stop"),
            (2, "2 stop (1 stop unavailable)"),
            (0, "Direct (1 stop and 2 stop unavailable)"),
        )
        for max_stops, default_label in fallback_order:
            results = await provider.search_round_trip(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                currency=currency,
                max_stops=max_stops,
                **self._provider_search_kwargs(provider, market=market),
            )
            if results:
                for result in results:
                    if not isinstance(result.raw_data, dict):
                        result.raw_data = {}
                    result.raw_data.setdefault("stop_result_label", default_label)
                return results, str(results[0].raw_data.get("stop_result_label") or default_label)
        return [], None

    # --------------------------------------------------
    # DB HELPERS
    # --------------------------------------------------

    async def _upsert_cheapest(
        self,
        session: AsyncSession,
        route_group_id: UUID,
        origin: str,
        destination: str,
        depart_date: date,
        result: ProviderResult,
    ) -> None:

        await session.execute(
            text("""
                INSERT INTO daily_cheapest_prices
                (
                    id,
                    route_group_id,
                    origin,
                    destination,
                    depart_date,
                    airline,
                    price,
                    currency,
                    provider,
                    deep_link,
                    stops,
                    stop_label,
                    duration_minutes,
                    scraped_at
                )
                VALUES
                (
                    gen_random_uuid(),
                    :route_group_id,
                    :origin,
                    :destination,
                    :depart_date,
                    :airline,
                    :price,
                    :currency,
                    :provider,
                    :deep_link,
                    :stops,
                    :stop_label,
                    :duration_minutes,
                    now()
                )
                ON CONFLICT (route_group_id, origin, destination, depart_date)
                DO UPDATE SET
                    airline = EXCLUDED.airline,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    provider = EXCLUDED.provider,
                    deep_link = EXCLUDED.deep_link,
                    stops = EXCLUDED.stops,
                    stop_label = EXCLUDED.stop_label,
                    duration_minutes = EXCLUDED.duration_minutes,
                    scraped_at = now()
            """),
            {
                "route_group_id": str(route_group_id),
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
                "airline": normalize_airline(result.airline),
                "price": result.price,
                "currency": result.currency,
                "provider": result.provider or "unknown",
                "deep_link": result.deep_link[:2048] if result.deep_link else None,
                "stops": result.stops,
                "stop_label": (
                    str(result.raw_data.get("stop_result_label"))
                    if isinstance(result.raw_data, dict) and result.raw_data.get("stop_result_label")
                    else None
                ),
                "duration_minutes": result.duration_minutes,
            },
        )

    async def _save_all_results(
        self,
        session: AsyncSession,
        route_group_id: UUID,
        origin: str,
        destination: str,
        depart_date: date,
        results: list[ProviderResult],
    ) -> None:

        await session.execute(
            text("""
                DELETE FROM all_flight_results
                WHERE route_group_id = :rg_id
                  AND origin = :origin
                  AND destination = :destination
                  AND depart_date = :depart_date
            """),
            {
                "rg_id": str(route_group_id),
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
            },
        )

        for result in sorted(results, key=lambda r: r.price):
            session.add(
                AllFlightResult(
                    route_group_id=route_group_id,
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    airline=normalize_airline(result.airline),
                    price=result.price,
                    currency=result.currency,
                    provider=result.provider or "unknown",
                    deep_link=result.deep_link[:2048] if result.deep_link else None,
                    stops=result.stops,
                    stop_label=(
                        str(result.raw_data.get("stop_result_label"))
                        if isinstance(result.raw_data, dict) and result.raw_data.get("stop_result_label")
                        else None
                    ),
                    duration_minutes=result.duration_minutes,
                    itinerary_data=result.raw_data if isinstance(result.raw_data, dict) else None,
                )
            )
