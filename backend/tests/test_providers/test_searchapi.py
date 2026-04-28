"""Tests for app.providers.serpapi — SerpAPI response parsing.

These tests mock httpx at the provider level so no real API calls are made.
The `_search_one_way_once` method is tested directly to bypass tenacity retries.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest

from app.providers.searchapi import SearchApiProvider


@pytest.fixture
def provider() -> SearchApiProvider:
    return SearchApiProvider(
        api_key="test-key",
        timeout=10,
        max_retries=1,
        concurrency_limit=2,
        min_delay_seconds=0,
    )


DEPART = date.today() + timedelta(days=30)


def mock_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = str(data)
    resp.raise_for_status = MagicMock()
    resp.headers = {}
    return resp


def make_flight_offer(
    price: int = 1200,
    airline: str = "Air Canada",
    flight_number: str = "AC 3",
    duration: int = 720,
    stops: int = 1,
    booking_token: str = "token123",
) -> dict:
    return {
        "price": price,
        "total_duration": duration,
        "booking_token": booking_token,
        "flights": [
            {"airline": airline, "flight_number": flight_number},
            *(
                [{"airline": airline, "flight_number": f"{flight_number}b"}]
                if stops >= 1
                else []
            ),
        ],
    }


# ── Response parsing ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_best_flights(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [make_flight_offer(price=800), make_flight_offer(price=950)],
        "other_flights": [],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert len(results) == 2
    assert results[0].price == 800
    assert results[1].price == 950


@pytest.mark.asyncio
async def test_parse_other_flights(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [],
        "other_flights": [make_flight_offer(price=1500)],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert len(results) == 1
    assert results[0].price == 1500


@pytest.mark.asyncio
async def test_airline_extracted_from_flight_number(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [make_flight_offer(flight_number="AC 123")],
        "other_flights": [],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    # Provider expands the IATA prefix from the flight number into the
    # human-readable airline name.
    assert results[0].airline == "Air Canada"


@pytest.mark.asyncio
async def test_stops_counted_from_flights_array(provider: SearchApiProvider) -> None:
    offer = make_flight_offer(stops=1)  # 2 segments = 1 stop
    data = {"best_flights": [offer], "other_flights": []}
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert results[0].stops == 1


@pytest.mark.asyncio
async def test_booking_token_deep_link(provider: SearchApiProvider) -> None:
    offer = make_flight_offer(booking_token="mytoken")
    data = {"best_flights": [offer], "other_flights": []}
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert "mytoken" in results[0].deep_link
    assert "google.com/travel/flights" in results[0].deep_link


@pytest.mark.asyncio
async def test_no_booking_token_fallback_link(provider: SearchApiProvider) -> None:
    offer = make_flight_offer(booking_token="")
    data = {"best_flights": [offer], "other_flights": []}
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert "google.com/flights" in results[0].deep_link


@pytest.mark.asyncio
async def test_offers_with_no_price_skipped(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [
            {"price": None, "flights": [{"airline": "AC", "flight_number": "AC 1"}], "total_duration": 600},
            make_flight_offer(price=500),
        ],
        "other_flights": [],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert len(results) == 1
    assert results[0].price == 500


@pytest.mark.asyncio
async def test_offers_with_no_flights_skipped(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [{"price": 500, "flights": [], "total_duration": 600}],
        "other_flights": [],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_empty_response(provider: SearchApiProvider) -> None:
    data = {"best_flights": [], "other_flights": []}
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert results == []


@pytest.mark.asyncio
async def test_invalid_json_returns_empty(provider: SearchApiProvider) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.side_effect = ValueError("bad json")
    resp.text = "not json"
    resp.raise_for_status = MagicMock()
    resp.headers = {}

    provider._client.get = AsyncMock(return_value=resp)

    results = await provider._search_one_way_once("YVR", "NRT", DEPART)
    assert results == []


# ── Error handling ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_429_raises_runtime_error(provider: SearchApiProvider) -> None:
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"Retry-After": "30"}

    provider._client.get = AsyncMock(return_value=resp)

    with pytest.raises(RuntimeError, match="rate limit"):
        await provider._search_one_way_once("YVR", "NRT", DEPART)


# ── Configuration checks ─────────────────────────────────────────────────────

def test_is_configured_true_with_key() -> None:
    assert SearchApiProvider(api_key="key").is_configured() is True


def test_is_configured_false_without_key() -> None:
    assert SearchApiProvider(api_key="").is_configured() is False


# ── Provider metadata ────────────────────────────────────────────────────────

def test_provider_name() -> None:
    assert SearchApiProvider.name == "searchapi"


def test_currency_passed_to_api(provider: SearchApiProvider) -> None:
    """Verify currency parameter is forwarded."""
    data = {"best_flights": [make_flight_offer()], "other_flights": []}
    resp = mock_response(data)
    provider._client.get = AsyncMock(return_value=resp)

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        provider._search_one_way_once("YVR", "NRT", DEPART, currency="CAD")
    )

    call_args = provider._client.get.call_args
    assert call_args[1]["params"]["currency"] == "CAD"


@pytest.mark.asyncio
async def test_close(provider: SearchApiProvider) -> None:
    provider._client.aclose = AsyncMock()
    await provider.close()
    provider._client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_multi_city_uses_single_provider_request(provider: SearchApiProvider) -> None:
    data = {
        "best_flights": [
            {
                "price": 829,
                "total_duration": 870,
                "booking_token": "book123",
                "flights": [
                    {"airline": "Icelandair", "flight_number": "FI 602", "layovers": [{"duration": 90}]},
                    {"airline": "Lufthansa", "flight_number": "LH 1677", "layovers": [{"duration": 75}]},
                ],
            }
        ],
        "other_flights": [],
    }
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_multi_city_once(
        [
            {"departure_id": "YYZ", "arrival_id": "BER", "outbound_date": DEPART},
            {"departure_id": "BUD", "arrival_id": "YYZ", "outbound_date": DEPART + timedelta(days=11)},
        ],
        currency="CAD",
        max_stops=1,
    )

    assert len(results) == 1
    assert results[0].price == 829
    assert results[0].stops == 2
    assert results[0].raw_data["stop_result_label"] == "1 stop"
    assert provider._client.get.await_count == 1


@pytest.mark.asyncio
async def test_multi_city_no_results_body_returns_empty(provider: SearchApiProvider) -> None:
    data = {"error": "Google Flights didn't return any results."}
    provider._client.get = AsyncMock(return_value=mock_response(data))

    results = await provider._search_multi_city_once(
        [
            {"departure_id": "YVR", "arrival_id": "TYO", "outbound_date": DEPART},
            {"departure_id": "SHA", "arrival_id": "YVR", "outbound_date": DEPART + timedelta(days=11)},
        ],
        currency="CAD",
        max_stops=1,
    )

    assert results == []
