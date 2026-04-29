from __future__ import annotations

import asyncio
import uuid
from datetime import date
from time import monotonic

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.logging import get_logger
from app.providers.base import ProviderResult

log = get_logger(__name__)


class ProviderQuotaExhaustedError(RuntimeError):
    pass


class ProviderAuthError(RuntimeError):
    pass


class ProviderRateLimitedError(RuntimeError):
    pass


class KayakProvider:
    name = "kayak"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        poll_timeout_seconds: int = 90,
        poll_interval_seconds: float = 2.0,
        user_agent: str = "flight-harvester/1.0",
        original_client_ip: str = "",
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._poll_timeout_seconds = max(5, poll_timeout_seconds)
        self._poll_interval_seconds = max(0.5, poll_interval_seconds)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent.strip() or "flight-harvester/1.0",
        }
        if original_client_ip.strip():
            headers["x-original-client-ip"] = original_client_ip.strip()
        self._client = httpx.AsyncClient(timeout=self._timeout, headers=headers)

    def is_configured(self) -> bool:
        return bool(self._api_key and self._base_url)

    @property
    def _poll_url(self) -> str:
        if self._base_url.endswith("/i/api/affiliate/search/flight/v1"):
            return f"{self._base_url}/poll"
        return f"{self._base_url}/i/api/affiliate/search/flight/v1/poll"

    def _passengers(self, adults: int) -> list[str]:
        return ["ADT"] * max(1, adults)

    def _cabin(self, cabin: str) -> str:
        return {
            "economy": "economy",
            "premium_economy": "premiumEconomy",
            "premiumeconomy": "premiumEconomy",
            "business": "business",
            "first": "first",
            "first_class": "first",
        }.get(cabin.lower(), "economy")

    def _location(self, code: str) -> dict[str, object]:
        return {
            "locationType": "airports",
            "airports": [code],
        }

    def _result_parameters(
        self,
        currency: str,
        max_stops: int | None,
    ) -> dict[str, object]:
        params: dict[str, object] = {
            "currency": currency,
            "priceMode": "total",
            "pageNumber": 1,
            "pageSize": 50,
            "sort": {
                "key": "price",
                "direction": "asc",
            },
        }
        if max_stops is not None:
            params["maxStops"] = max(0, min(2, int(max_stops)))
        return params

    def _message_from_payload(self, payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None

        error_message = payload.get("errorMessage")
        if isinstance(error_message, str) and error_message.strip():
            return error_message.strip()

        errors = payload.get("errors")
        if isinstance(errors, list):
            parts: list[str] = []
            for item in errors:
                if isinstance(item, dict):
                    text = item.get("localizedDescription") or item.get("description") or item.get("code")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "; ".join(parts)

        return None

    def _raise_for_response(
        self,
        response: httpx.Response,
        payload: object,
    ) -> None:
        message = self._message_from_payload(payload) or response.text or "KAYAK request failed."

        if response.status_code in {401, 403}:
            raise ProviderAuthError(message)
        if response.status_code == 429:
            raise ProviderRateLimitedError(message)
        if response.status_code >= 400:
            raise RuntimeError(message)

    async def _post_json(
        self,
        params: dict[str, object],
        payload: dict[str, object],
    ) -> dict:
        try:
            response = await self._client.post(self._poll_url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise RuntimeError("KAYAK request timed out.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("KAYAK request failed.") from exc

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError("KAYAK returned invalid JSON.") from exc

        self._raise_for_response(response, data)
        return data if isinstance(data, dict) else {}

    def _option_price(self, option: dict[str, object]) -> float | None:
        fees = option.get("fees")
        if isinstance(fees, dict):
            total_price = fees.get("totalPrice")
            if isinstance(total_price, dict):
                value = total_price.get("price")
                if isinstance(value, (int, float)) and value >= 0:
                    return float(value)

        display_price = option.get("displayPrice")
        if isinstance(display_price, dict):
            value = display_price.get("price")
            if isinstance(value, (int, float)) and value >= 0:
                return float(value)

        return None

    def _choose_regular_option(self, result: dict[str, object]) -> tuple[dict[str, object], float] | None:
        best: tuple[dict[str, object], float] | None = None
        for option in result.get("bookingOptions", []):
            if not isinstance(option, dict):
                continue
            if option.get("type") != "regular":
                continue
            price = self._option_price(option)
            if price is None:
                continue
            if best is None or price < best[1]:
                best = (option, price)
        return best

    def _airline_name(self, code: str, airlines: dict[str, object]) -> str:
        airline = airlines.get(code)
        if isinstance(airline, dict):
            display_name = airline.get("displayName")
            if isinstance(display_name, str) and display_name.strip():
                return display_name.strip()
        return code

    def _build_result(
        self,
        *,
        result: dict[str, object],
        legs_map: dict[str, object],
        segments_map: dict[str, object],
        airlines_map: dict[str, object],
        search_id: str,
        cluster: str,
        currency: str,
        trip_type: str,
    ) -> ProviderResult | None:
        chosen = self._choose_regular_option(result)
        if not chosen:
            return None

        option, price = chosen
        booking_url = option.get("bookingUrl")
        if not isinstance(booking_url, str) or not booking_url.strip():
            return None

        result_legs = result.get("legs", [])
        if not isinstance(result_legs, list) or not result_legs:
            return None

        leg_ids: list[str] = []
        total_duration = 0
        total_stops = 0
        first_airline = ""
        last_airline = ""

        for index, leg_ref in enumerate(result_legs):
            if not isinstance(leg_ref, dict):
                continue
            leg_id = leg_ref.get("id")
            if not isinstance(leg_id, str):
                continue
            leg_ids.append(leg_id)
            leg = legs_map.get(leg_id)
            if not isinstance(leg, dict):
                continue

            duration = leg.get("duration")
            if isinstance(duration, (int, float)):
                total_duration += int(duration)

            segments = leg.get("segments", [])
            if isinstance(segments, list) and segments:
                total_stops += max(0, len(segments) - 1)
                first_segment_id = segments[0].get("id") if isinstance(segments[0], dict) else None
                last_segment_id = segments[-1].get("id") if isinstance(segments[-1], dict) else None
                first_segment = segments_map.get(first_segment_id) if isinstance(first_segment_id, str) else None
                last_segment = segments_map.get(last_segment_id) if isinstance(last_segment_id, str) else None

                if index == 0 and isinstance(first_segment, dict):
                    airline_code = first_segment.get("airline")
                    if isinstance(airline_code, str):
                        first_airline = self._airline_name(airline_code, airlines_map)

                if index == len(result_legs) - 1 and isinstance(last_segment, dict):
                    airline_code = last_segment.get("airline")
                    if isinstance(airline_code, str):
                        last_airline = self._airline_name(airline_code, airlines_map)

        if not first_airline:
            first_airline = last_airline
        if not last_airline:
            last_airline = first_airline

        if trip_type == "one_way":
            airline = first_airline
        else:
            airline = f"{first_airline} / {last_airline}".strip(" /")

        raw_data: dict[str, object] = {
            "search_id": search_id,
            "cluster": cluster,
            "result_id": result.get("id"),
            "provider_code": option.get("providerCode"),
            "trip_type": trip_type,
            "leg_ids": leg_ids,
        }
        if trip_type == "multi_city":
            raw_data["outbound_airline"] = first_airline
            raw_data["return_airline"] = last_airline

        return ProviderResult(
            price=price,
            currency=currency,
            airline=airline,
            deep_link=booking_url.strip(),
            provider=self.name,
            duration_minutes=total_duration,
            stops=total_stops,
            raw_data=raw_data,
        )

    def _parse_results(
        self,
        payload: dict[str, object],
        *,
        currency: str,
        trip_type: str,
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        results = payload.get("results", [])
        if not isinstance(results, list) or not results:
            return []

        legs_map = payload.get("legs") if isinstance(payload.get("legs"), dict) else {}
        segments_map = payload.get("segments") if isinstance(payload.get("segments"), dict) else {}
        airlines_map = payload.get("airlines") if isinstance(payload.get("airlines"), dict) else {}
        search_id = str(payload.get("searchId") or "")
        cluster = str(payload.get("cluster") or "")

        normalized: list[ProviderResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            parsed = self._build_result(
                result=item,
                legs_map=legs_map,
                segments_map=segments_map,
                airlines_map=airlines_map,
                search_id=search_id,
                cluster=cluster,
                currency=currency,
                trip_type=trip_type,
            )
            if parsed:
                normalized.append(parsed)

        if max_stops == 2:
            normalized = [item for item in normalized if item.stops <= 2]

        return sorted(normalized, key=lambda item: item.price)

    async def _search(
        self,
        *,
        legs: list[dict[str, object]],
        adults: int,
        cabin: str,
        currency: str,
        max_stops: int | None,
        trip_type: str,
    ) -> list[ProviderResult]:
        if not self.is_configured():
            return []

        start_params = {
            "cabin": self._cabin(cabin),
            "passengers": self._passengers(adults),
            "legs": [
                {
                    "origin": self._location(str(leg["departure_id"])),
                    "destination": self._location(str(leg["arrival_id"])),
                    "date": leg["outbound_date"].isoformat(),
                }
                for leg in legs
            ],
            "filters": {
                "includeSplit": False,
            },
        }
        result_params = self._result_parameters(currency, max_stops)
        user_track_id = str(uuid.uuid4())
        query = {
            "apiKey": self._api_key,
            "userTrackId": user_track_id,
        }

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=1, max=8),
            retry=retry_if_exception_type((RuntimeError, ProviderRateLimitedError)),
            reraise=True,
        ):
            with attempt:
                payload = await self._post_json(
                    query,
                    {
                        "searchStartParameters": start_params,
                        "resultParameters": result_params,
                    },
                )

                search_id = payload.get("searchId")
                cluster = payload.get("cluster")
                if not isinstance(search_id, str) or not search_id.strip():
                    return self._parse_results(payload, currency=currency, trip_type=trip_type, max_stops=max_stops)

                latest_payload = payload
                deadline = monotonic() + self._poll_timeout_seconds
                while latest_payload.get("status") != "complete":
                    if monotonic() >= deadline:
                        parsed = self._parse_results(latest_payload, currency=currency, trip_type=trip_type, max_stops=max_stops)
                        if parsed:
                            return parsed
                        raise RuntimeError("KAYAK polling timed out before returning complete results.")

                    await asyncio.sleep(self._poll_interval_seconds)

                    poll_query = {
                        "apiKey": self._api_key,
                        "userTrackId": user_track_id,
                    }
                    if isinstance(cluster, str) and cluster.strip():
                        poll_query["cluster"] = cluster

                    latest_payload = await self._post_json(
                        poll_query,
                        {
                            "searchId": search_id,
                            "resultParameters": result_params,
                        },
                    )
                    cluster = latest_payload.get("cluster") or cluster

                parsed = self._parse_results(latest_payload, currency=currency, trip_type=trip_type, max_stops=max_stops)
                log.info(
                    "kayak_results",
                    trip_type=trip_type,
                    origin=str(legs[0]["departure_id"]),
                    destination=str(legs[0]["arrival_id"]),
                    count=len(parsed),
                    currency=currency,
                )
                return parsed

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
        return await self._search(
            legs=[
                {
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": depart_date,
                }
            ],
            adults=adults,
            cabin=cabin,
            currency=currency,
            max_stops=max_stops,
            trip_type="one_way",
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
        return await self._search(
            legs=[
                {
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": depart_date,
                },
                {
                    "departure_id": destination,
                    "arrival_id": origin,
                    "outbound_date": return_date,
                },
            ],
            adults=adults,
            cabin=cabin,
            currency=currency,
            max_stops=max_stops,
            trip_type="round_trip",
        )

    async def search_multi_city(
        self,
        legs: list[dict[str, object]],
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        if len(legs) != 2:
            return []
        return await self._search(
            legs=legs,
            adults=adults,
            cabin=cabin,
            currency=currency,
            max_stops=max_stops,
            trip_type="multi_city",
        )

    async def close(self) -> None:
        await self._client.aclose()
