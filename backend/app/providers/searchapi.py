"""
SearchApi.io Google Flights provider.
Upgraded version with:
- quota circuit breaker
- cooldown after quota hit
- safer retries
- cleaner errors
- rate-limit handling
- better logging
"""

from __future__ import annotations

import asyncio
from datetime import date
from time import monotonic
from urllib.parse import quote

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.logging import get_logger
from app.providers.base import ProviderResult

log = get_logger(__name__)

_BASE_URL = "https://www.searchapi.io/api/v1/search"


class ProviderQuotaExhaustedError(RuntimeError):
    pass


class ProviderAuthError(RuntimeError):
    pass


class ProviderRateLimitedError(RuntimeError):
    pass


def _extract_body_error(resp: httpx.Response) -> str | None:
    try:
        payload = resp.json()
    except Exception:
        return None

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()

    return None


def _retry_after_seconds(headers: httpx.Headers | dict[str, str], default: int = 60) -> int:
    raw = headers.get("Retry-After", default)
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, seconds)


def _classify_error_message(message: str) -> type[RuntimeError]:
    lowered = message.lower()

    if (
        "run out of searches" in lowered
        or "used all of the searches" in lowered
        or "upgrade" in lowered
        or "plan requires" in lowered
        or "quota" in lowered
    ):
        return ProviderQuotaExhaustedError

    if (
        "invalid api key" in lowered
        or "missing api_key" in lowered
        or "unauthorized" in lowered
        or "forbidden" in lowered
    ):
        return ProviderAuthError

    if (
        "rate limit" in lowered
        or "too many requests" in lowered
    ):
        return ProviderRateLimitedError

    return RuntimeError


class SearchApiProvider:
    name = "searchapi"

    _STOPS_MAP: dict[int | None, str] = {
        None: "any",
        0: "nonstop",
        1: "one_stop_or_fewer",
        2: "two_stops_or_fewer",
    }

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        concurrency_limit: int = 2,
        min_delay_seconds: float = 1.0,
        quota_cooldown_seconds: int = 3600,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=self._timeout)

        self._semaphore = asyncio.Semaphore(max(1, concurrency_limit))
        self._throttle_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._min_delay_seconds = max(0.0, min_delay_seconds)

        # Circuit breaker
        self._quota_blocked_until = 0.0
        self._quota_cooldown_seconds = quota_cooldown_seconds

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _quota_blocked(self) -> bool:
        return monotonic() < self._quota_blocked_until

    def _trip_quota_breaker(self) -> None:
        self._quota_blocked_until = monotonic() + self._quota_cooldown_seconds

    async def _wait_for_slot(self) -> None:
        async with self._throttle_lock:
            now = monotonic()
            wait_for = self._next_request_at - now

            if wait_for > 0:
                await asyncio.sleep(wait_for)

            self._next_request_at = monotonic() + self._min_delay_seconds

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:

        if self._quota_blocked():
            raise ProviderQuotaExhaustedError(
                "SearchApi quota previously exhausted. Cooldown active."
            )

        def _should_retry(exc: BaseException) -> bool:
            return isinstance(exc, RuntimeError) and not isinstance(
                exc,
                (
                    ProviderQuotaExhaustedError,
                    ProviderAuthError,
                ),
            )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=2, max=20),
            retry=retry_if_exception_type(RuntimeError)
            & retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                return await self._search_one_way_once(
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    adults=adults,
                    cabin=cabin,
                    currency=currency,
                    max_stops=max_stops,
                )
        return []

    async def search_round_trip(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,          
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:

        if self._quota_blocked():
            raise ProviderQuotaExhaustedError(
                "SearchApi quota previously exhausted. Cooldown active."
            )

        def _should_retry(exc: BaseException) -> bool:
            return isinstance(exc, RuntimeError) and not isinstance(
                exc,
                (
                    ProviderQuotaExhaustedError,
                    ProviderAuthError,
                ),
            )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=2, max=20),
            retry=retry_if_exception_type(RuntimeError)
            & retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                return await self._search_round_trip_once(
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    return_date=return_date,
                    adults=adults,
                    cabin=cabin,
                    currency=currency,
                    max_stops=max_stops,
                )

        return []

    async def _search_round_trip_once(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:

        if self._quota_blocked():
            raise ProviderQuotaExhaustedError(
                "SearchApi quota cooldown active."
            )

        travel_class_map = {
            "economy": "economy",
            "premium_economy": "premium_economy",
            "business": "business",
            "first": "first_class",
        }

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": depart_date.isoformat(),
            "return_date": return_date.isoformat(),
            "currency": currency,
            "adults": adults,
            "flight_type": "round_trip",
            "travel_class": travel_class_map.get(
                cabin.lower(),  
                "economy",
            ),
            "stops": self._STOPS_MAP.get(max_stops, "any"),
            "api_key": self._api_key,
        }

        async with self._semaphore:
            await self._wait_for_slot()

            try:
                resp = await self._client.get(
                    _BASE_URL,
                    params=params,
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    "SearchApi request timed out."
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    "SearchApi request failed."
                ) from exc

        body_error = _extract_body_error(resp)

        if resp.status_code in (401, 403):
            raise ProviderAuthError(
                body_error or "SearchApi authentication failed."
            )

        if resp.status_code == 429:
            err_cls = _classify_error_message(body_error or "")

            if err_cls is ProviderQuotaExhaustedError:
                self._trip_quota_breaker()

                raise ProviderQuotaExhaustedError(
                    body_error or "SearchApi quota exhausted."
                )

            retry_after = _retry_after_seconds(resp.headers)

            log.warning(
                "searchapi_rate_limited",
                retry_after=retry_after,
            )

            raise ProviderRateLimitedError(
                f"SearchApi rate limit hit. Retry after {retry_after}s."
            )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"SearchApi returned status {resp.status_code}."
            )

        try:
            data = resp.json()
        except Exception:
            return []

        if isinstance(data, dict) and data.get("error"):
            err_text = str(data["error"])
            err_cls = _classify_error_message(err_text)

            if err_cls is ProviderQuotaExhaustedError:
                self._trip_quota_breaker()

            raise err_cls(err_text)

        results: list[ProviderResult] = []

        for section in ("best_flights", "other_flights"):
            for offer in data.get(section, []):
                price = offer.get("price")
                if price is None:
                    continue

                flights = offer.get("flights", [])
                if not flights:
                    continue

                first_leg = flights[0]

                flight_number = first_leg.get(
                    "flight_number",
                    "",
                )

                airline_name = first_leg.get(
                    "airline",
                    "",
                )

                airline = airline_name.strip() or (
                    flight_number.split()[0]
                    if flight_number
                    else ""
                )

                total_duration = offer.get(
                    "total_duration",
                    0,
                )

                stops = max(0, len(flights) - 1)

                booking_token = offer.get(
                    "booking_token",
                    "",
                )

                if booking_token:
                    deep_link = (
                        "https://www.google.com/travel/flights"
                        f"?tfs={booking_token}"
                    )
                else:
                    deep_link = (
                        f"https://www.google.com/flights"
                    )

                results.append(
                    ProviderResult(
                        price=float(price),
                        currency=currency,
                        airline=airline,
                        deep_link=deep_link,
                        provider=self.name,
                        stops=stops,
                        duration_minutes=int(total_duration),
                        raw_data={
                            "trip_type": "round_trip",
                            "section": section,
                        },
                    )
                )
        log.info(
            "searchapi_results",
            trip_type="round_trip",
            origin=origin,
            destination=destination,
            depart_date=depart_date.isoformat(),
            return_date=return_date.isoformat(),
            count=len(results),
            currency=currency,
        )

        return results  

    async def _search_one_way_once(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        """
        Search Google Flights for one-way flights.
        Rate-limited and retried with exponential backoff.
        """
        if self._quota_blocked():
            raise ProviderQuotaExhaustedError(
                "SearchApi quota cooldown active."
            )

        travel_class_map = {
            "economy": "economy",
            "premium_economy": "premium_economy",
            "business": "business",
            "first": "first_class",
        }

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": depart_date.isoformat(),
            "currency": currency,
            "adults": adults,
            "flight_type": "one_way",
            "travel_class": travel_class_map.get(
                cabin.lower(),
                "economy",
            ),
            "stops": self._STOPS_MAP.get(max_stops, "any"),
            "api_key": self._api_key,
        }

        async with self._semaphore:
            await self._wait_for_slot()

            try:
                resp = await self._client.get(
                    _BASE_URL,
                    params=params,
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    "SearchApi request timed out."
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    "SearchApi request failed."
                ) from exc

        body_error = _extract_body_error(resp)

        # Auth / Forbidden
        if resp.status_code in (401, 403):
            raise ProviderAuthError(
                body_error or "SearchApi authentication failed."
            )

        # Rate limit
        if resp.status_code == 429:
            err_cls = _classify_error_message(body_error or "")

            if err_cls is ProviderQuotaExhaustedError:
                self._trip_quota_breaker()

                log.warning(
                    "searchapi_quota_exhausted",
                    cooldown_seconds=self._quota_cooldown_seconds,
                )

                raise ProviderQuotaExhaustedError(
                    body_error or "SearchApi quota exhausted."
                )

            retry_after = _retry_after_seconds(resp.headers)

            log.warning(
                "searchapi_rate_limited",
                retry_after=retry_after,
            )

            raise ProviderRateLimitedError(
                f"SearchApi rate limit hit. Retry after {retry_after}s."
            )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"SearchApi returned status {resp.status_code}."
            )

        try:
            data = resp.json()
        except Exception:
            log.warning(
                "searchapi_invalid_json",
                preview=resp.text[:200],
            )
            return []

        # Body-level error
        if isinstance(data, dict) and data.get("error"):
            err_text = str(data["error"])
            err_cls = _classify_error_message(err_text)

            if err_cls is ProviderQuotaExhaustedError:
                self._trip_quota_breaker()

            raise err_cls(err_text)

        results: list[ProviderResult] = []

        for section in ("best_flights", "other_flights"):
            for offer in data.get(section, []):
                price = offer.get("price")

                if price is None:
                    continue

                flights = offer.get("flights", [])

                if not flights:
                    continue

                first_leg = flights[0]

                flight_number = first_leg.get(
                    "flight_number",
                    "",
                )

                airline_name = first_leg.get(
                    "airline",
                    "",
                )

                airline = airline_name.strip() or (
                    flight_number.split()[0]
                    if flight_number
                    else ""
                )

                total_duration = offer.get(
                    "total_duration",
                    0,
                )

                stops = max(0, len(flights) - 1)

                booking_token = offer.get(
                    "booking_token",
                    "",
                )

                if booking_token:
                    deep_link = (
                        "https://www.google.com/travel/flights"
                        f"?tfs={booking_token}"
                    )
                else:
                    deep_link = (
                        f"https://www.google.com/flights#search;"
                        f"f={quote(origin)};"
                        f"t={quote(destination)};"
                        f"d={depart_date.isoformat()};tt=o"
                    )

                results.append(
                    ProviderResult(
                        price=float(price),
                        currency=currency,
                        airline=airline,
                        deep_link=deep_link,
                        provider=self.name,
                        stops=stops,
                        duration_minutes=int(total_duration),
                        raw_data={
                            "flight_number": flight_number,
                            "section": section,
                        },
                    )
                )
        log.info(
            "searchapi_results",
            trip_type="one_way",
            origin=origin,
            destination=destination,
            date=depart_date.isoformat(),
            count=len(results),
            currency=currency,
        )

        return results

    async def close(self) -> None:
        await self._client.aclose()


class SearchApiPoolProvider:
    name = "searchapi"

    def __init__(
        self,
        api_keys: list[str],
        timeout: int = 30,
        max_retries: int = 3,
        concurrency_limit: int = 2,
        min_delay_seconds: float = 1.0,
        quota_cooldown_seconds: int = 3600,
    ) -> None:
        self._providers = [
            SearchApiProvider(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                concurrency_limit=concurrency_limit,
                min_delay_seconds=min_delay_seconds,
                quota_cooldown_seconds=quota_cooldown_seconds,
            )
            for api_key in api_keys
            if api_key.strip()
        ]
        self._cursor = 0

    def is_configured(self) -> bool:
        return any(provider.is_configured() for provider in self._providers)

    def _ordered_providers(self) -> list[SearchApiProvider]:
        if not self._providers:
            return []

        start = self._cursor % len(self._providers)
        self._cursor = (self._cursor + 1) % len(self._providers)
        return self._providers[start:] + self._providers[:start]

    async def _search_with_failover(self, search_fn) -> list[ProviderResult]:
        last_exc: BaseException | None = None

        for provider in self._ordered_providers():
            try:
                return await search_fn(provider)
            except (
                ProviderQuotaExhaustedError,
                ProviderAuthError,
                ProviderRateLimitedError,
                RuntimeError,
            ) as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise last_exc

        return []

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        return await self._search_with_failover(
            lambda provider: provider.search_one_way(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                adults=adults,
                cabin=cabin,
                currency=currency,
                max_stops=max_stops,
            )
        )

    async def search_round_trip(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        return await self._search_with_failover(
            lambda provider: provider.search_round_trip(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                adults=adults,
                cabin=cabin,
                currency=currency,
                max_stops=max_stops,
            )
        )

    async def close(self) -> None:
        for provider in self._providers:
            await provider.close()
