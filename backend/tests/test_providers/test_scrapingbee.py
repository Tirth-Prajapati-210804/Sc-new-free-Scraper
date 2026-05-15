from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.base import ProviderQuotaExhaustedError, ProviderRateLimitedError
from app.providers.scrapingbee import ScrapingBeeProvider


@pytest.fixture
def provider() -> ScrapingBeeProvider:
    return ScrapingBeeProvider(
        api_key="test-key",
        timeout=10,
        max_retries=1,
        concurrency_limit=2,
        min_delay_seconds=0,
    )


DEPART = date.today() + timedelta(days=30)


def mock_response(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


@pytest.mark.asyncio
async def test_parse_one_way_offer(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response(
            {
                "offers": [
                    {
                        "price": 812,
                        "airline": "Air Canada",
                        "duration": 735,
                        "duration_text": "12h 15m",
                        "stops": 0,
                        "summary": "Air Canada nonstop",
                        "link": "/book/flight-123",
                    }
                ]
            }
        )
    )

    results = await provider._search_one_way_once(
        "YVR",
        "NRT",
        DEPART,
        market="ca",
        currency="CAD",
    )

    assert len(results) == 1
    assert results[0].price == 812.0
    assert results[0].currency == "CAD"
    assert results[0].airline == "Air Canada"
    assert results[0].stops == 0
    assert results[0].duration_minutes == 735
    assert results[0].provider == "scrapingbee"
    assert results[0].deep_link.startswith("https://www.ca.kayak.com/")


@pytest.mark.asyncio
async def test_explicit_market_overrides_currency_domain(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(return_value=mock_response({"offers": []}))

    await provider._search_one_way_once(
        "YVR",
        "DPS",
        DEPART,
        market="ca",
        currency="USD",
    )

    params = provider._client.get.call_args.kwargs["params"]

    assert params["url"].startswith("https://www.ca.kayak.com/flights/YVR-DPS/")
    assert params["country_code"] == "ca"


@pytest.mark.asyncio
async def test_parse_one_way_offer_detects_market_currency_from_symbol(
    provider: ScrapingBeeProvider,
) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response(
            {
                "offers": [
                    {
                        "price": 93128,
                        "price_text": "₹93,128",
                        "airline": "Cathay Pacific",
                        "duration": 1225,
                        "duration_text": "20h 25m",
                        "stops": 1,
                        "summary": "Cathay Pacific 1 stop",
                        "link": "/book/flight-456",
                    }
                ]
            }
        )
    )

    results = await provider._search_one_way_once("YVR", "DPS", DEPART, currency="USD")

    params = provider._client.get.call_args.kwargs["params"]

    assert params["url"].startswith("https://www.kayak.com/flights/YVR-DPS/")
    assert params["country_code"] == "us"
    assert len(results) == 1
    assert results[0].price == 93128.0
    assert results[0].currency == "INR"
    assert results[0].raw_data["price_text"] == "₹93,128"


@pytest.mark.asyncio
async def test_max_stops_filters_results(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response(
            {
                "offers": [
                    {
                        "price": 500,
                        "airline": "Air Canada",
                        "duration_text": "8h 5m",
                        "stops": 1,
                        "summary": "Air Canada 1 stop",
                        "link": "/flights/one",
                    },
                    {
                        "price": 650,
                        "airline": "Lufthansa",
                        "duration_text": "12h 20m",
                        "stops": 2,
                        "summary": "Lufthansa 2 stops",
                        "link": "/flights/two",
                    },
                ]
            }
        )
    )

    results = await provider.search_one_way(
        origin="YVR",
        destination="NRT",
        depart_date=DEPART,
        max_stops=1,
    )

    assert len(results) == 1
    assert results[0].airline == "Air Canada"


@pytest.mark.asyncio
async def test_round_trip_builds_round_trip_search_url(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(return_value=mock_response({"offers": []}))

    await provider._search_round_trip_once(
        "YYZ",
        "DPS",
        DEPART,
        DEPART + timedelta(days=12),
        currency="USD",
    )

    params = provider._client.get.call_args.kwargs["params"]
    target_url = params["url"]
    assert "kayak.com/flights/YYZ-DPS/" in target_url
    assert f"/{DEPART:%Y-%m-%d}/{DEPART + timedelta(days=12):%Y-%m-%d}" in target_url
    assert "sort=price_a" in target_url
    assert isinstance(params["ai_extract_rules"], str)
    assert isinstance(params["js_scenario"], str)


@pytest.mark.asyncio
async def test_401_maps_to_quota_exhausted(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response({"message": "No more credit available"}, status_code=401)
    )

    with pytest.raises(ProviderQuotaExhaustedError):
        await provider._search_one_way_once("YVR", "NRT", DEPART)


@pytest.mark.asyncio
async def test_429_maps_to_rate_limited(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response({"message": "Too many concurrent requests"}, status_code=429)
    )

    with pytest.raises(ProviderRateLimitedError):
        await provider._search_one_way_once("YVR", "NRT", DEPART)


@pytest.mark.asyncio
async def test_multi_city_uses_native_kayak_search(provider: ScrapingBeeProvider) -> None:
    provider._client.get = AsyncMock(
        return_value=mock_response(
            {
                "evaluate_results": [
                    json.dumps(
                        {
                            "cards": [
                                {
                                    "text": (
                                        "Best Cheapest 8:30 pm - 11:10 am+1 "
                                        "YYZ Toronto Pearson - BER Berlin Brandenburg "
                                        "1 stop 13h 40m "
                                        "9:15 am - 1:34 pm "
                                        "BUD Budapest Ferenc Liszt Intl - YYZ Toronto Pearson "
                                        "1 stop 10h 19m "
                                        "$829 Economy Light Select"
                                    ),
                                    "price_text": "$829",
                                    "booking_href": "/book/open-jaw-123",
                                    "cabin": "Economy Light",
                                    "airline_text": "Icelandair / Lufthansa",
                                    "legs": [
                                        {
                                            "text": (
                                                "8:30 pm - 11:10 am+1 "
                                                "YYZ Toronto Pearson - BER Berlin Brandenburg "
                                                "1 stop 13h 40m"
                                            ),
                                            "airline": "Icelandair",
                                            "time_text": "8:30 pm - 11:10 am+1",
                                            "route_text": "YYZ Toronto Pearson - BER Berlin Brandenburg",
                                            "stops_text": "1 stop",
                                            "layover_text": "KEF 1h 15m layover, Reykjavik Keflavik Intl",
                                            "duration_text": "13h 40m",
                                        },
                                        {
                                            "text": (
                                                "9:15 am - 1:34 pm "
                                                "BUD Budapest Ferenc Liszt Intl - YYZ Toronto Pearson "
                                                "1 stop 10h 19m"
                                            ),
                                            "airline": "Lufthansa",
                                            "time_text": "9:15 am - 1:34 pm",
                                            "route_text": "BUD Budapest Ferenc Liszt Intl - YYZ Toronto Pearson",
                                            "stops_text": "1 stop",
                                            "layover_text": "MUC 55m layover, Munich",
                                            "duration_text": "10h 19m",
                                        },
                                    ],
                                }
                            ]
                        }
                    )
                ]
            }
        )
    )

    results = await provider.search_multi_city(
        [
            {"departure_id": "YYZ", "arrival_id": "BER", "outbound_date": DEPART},
            {
                "departure_id": "BUD",
                "arrival_id": "YYZ",
                "outbound_date": DEPART + timedelta(days=11),
            },
        ],
        currency="USD",
        market="ca",
    )

    params = provider._client.get.call_args.kwargs["params"]

    assert len(results) == 1
    assert (
        params["url"]
        == f"https://www.ca.kayak.com/flights/YYZ-BER/{DEPART:%Y-%m-%d}/BUD-YYZ/{DEPART + timedelta(days=11):%Y-%m-%d}?sort=price_a"
    )
    assert params["country_code"] == "ca"
    assert params["json_response"] == "True"
    assert "Result item" in params["js_scenario"]
    assert "nrc6-price-section" in params["js_scenario"]
    assert "scrollTo" in params["js_scenario"]
    assert "slice(0,60)" in params["js_scenario"]
    assert results[0].price == 829.0
    assert results[0].airline == "Icelandair / Lufthansa"
    assert results[0].duration_minutes == 1439
    assert results[0].stops == 1
    assert results[0].deep_link == "https://www.ca.kayak.com/book/open-jaw-123"
    assert results[0].raw_data["cabin"] == "Economy Light"
    assert len(results[0].raw_data["legs"]) == 2
    assert results[0].raw_data["outbound_airline"] == "Icelandair"
    assert results[0].raw_data["return_airline"] == "Lufthansa"
    assert results[0].raw_data["return_origin"] == "BUD"
    assert results[0].raw_data["return_destination"] == "YYZ"
    assert results[0].raw_data["return_date"] == (DEPART + timedelta(days=11)).isoformat()


def test_is_configured(provider: ScrapingBeeProvider) -> None:
    assert provider.is_configured() is True
    assert ScrapingBeeProvider(api_key="").is_configured() is False
