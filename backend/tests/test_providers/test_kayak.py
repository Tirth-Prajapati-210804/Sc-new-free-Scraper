from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.providers.kayak import KayakProvider


@pytest.fixture
def provider() -> KayakProvider:
    return KayakProvider(
        api_key="test-key",
        base_url="https://sandbox-en-us.kayakaffiliates.com",
        timeout=5,
        max_retries=1,
        poll_timeout_seconds=5,
        poll_interval_seconds=0.01,
    )


def _complete_payload(results: list[dict], legs: dict, segments: dict, airlines: dict) -> dict:
    return {
        "searchId": "search-123",
        "cluster": "cluster-a",
        "status": "complete",
        "results": results,
        "legs": legs,
        "segments": segments,
        "airlines": airlines,
    }


@pytest.mark.asyncio
async def test_search_one_way_polls_and_parses_results(provider: KayakProvider) -> None:
    calls: list[tuple[dict[str, object], dict[str, object]]] = []

    async def fake_post_json(params: dict[str, object], payload: dict[str, object]) -> dict:
        calls.append((params, payload))
        if len(calls) == 1:
            return {
                "searchId": "search-123",
                "cluster": "cluster-a",
                "status": "first-phase",
                "results": [],
            }
        return _complete_payload(
            results=[
                {
                    "id": "result-1",
                    "legs": [{"id": "leg-1"}],
                    "bookingOptions": [
                        {
                            "type": "regular",
                            "bookingUrl": "https://kayak.test/booking",
                            "displayPrice": {"price": 1149},
                            "providerCode": "KA",
                        }
                    ],
                }
            ],
            legs={
                "leg-1": {
                    "duration": 615,
                    "segments": [{"id": "seg-1"}, {"id": "seg-2"}],
                }
            },
            segments={
                "seg-1": {"airline": "AC"},
                "seg-2": {"airline": "AC"},
            },
            airlines={"AC": {"displayName": "Air Canada"}},
        )

    provider._post_json = AsyncMock(side_effect=fake_post_json)  # type: ignore[method-assign]

    results = await provider.search_one_way(
        origin="YYZ",
        destination="BER",
        depart_date=date(2026, 10, 3),
        currency="CAD",
        max_stops=1,
    )

    assert len(calls) == 2
    assert calls[0][0]["apiKey"] == "test-key"
    assert isinstance(calls[0][0]["userTrackId"], str) and calls[0][0]["userTrackId"]
    assert calls[0][1]["searchStartParameters"]["legs"][0]["date"] == "2026-10-03"
    assert calls[0][1]["resultParameters"]["currency"] == "CAD"
    assert len(results) == 1
    assert results[0].price == 1149
    assert results[0].currency == "CAD"
    assert results[0].airline == "Air Canada"
    assert results[0].stops == 1
    assert results[0].duration_minutes == 615


@pytest.mark.asyncio
async def test_max_stops_two_filters_out_results_above_two_stops(provider: KayakProvider) -> None:
    provider._post_json = AsyncMock(  # type: ignore[method-assign]
        return_value=_complete_payload(
            results=[
                {
                    "id": "too-many-stops",
                    "legs": [{"id": "leg-3stops"}],
                    "bookingOptions": [
                        {
                            "type": "regular",
                            "bookingUrl": "https://kayak.test/three-stops",
                            "displayPrice": {"price": 900},
                            "providerCode": "KA",
                        }
                    ],
                },
                {
                    "id": "two-stops",
                    "legs": [{"id": "leg-2stops"}],
                    "bookingOptions": [
                        {
                            "type": "regular",
                            "bookingUrl": "https://kayak.test/two-stops",
                            "displayPrice": {"price": 1000},
                            "providerCode": "KA",
                        }
                    ],
                },
            ],
            legs={
                "leg-3stops": {
                    "duration": 900,
                    "segments": [
                        {"id": "seg-a1"},
                        {"id": "seg-a2"},
                        {"id": "seg-a3"},
                        {"id": "seg-a4"},
                    ],
                },
                "leg-2stops": {
                    "duration": 700,
                    "segments": [
                        {"id": "seg-b1"},
                        {"id": "seg-b2"},
                        {"id": "seg-b3"},
                    ],
                },
            },
            segments={
                "seg-a1": {"airline": "AC"},
                "seg-a2": {"airline": "AC"},
                "seg-a3": {"airline": "AC"},
                "seg-a4": {"airline": "AC"},
                "seg-b1": {"airline": "AC"},
                "seg-b2": {"airline": "AC"},
                "seg-b3": {"airline": "AC"},
            },
            airlines={"AC": {"displayName": "Air Canada"}},
        )
    )

    results = await provider.search_one_way(
        origin="YYZ",
        destination="BER",
        depart_date=date(2026, 10, 3),
        currency="CAD",
        max_stops=2,
    )

    assert [result.price for result in results] == [1000]
    assert results[0].stops == 2
