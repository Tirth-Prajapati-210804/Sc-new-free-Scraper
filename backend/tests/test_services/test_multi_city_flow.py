from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from app.providers.base import ProviderResult
from app.services.export_service import export_route_group
from app.services.price_collector import PriceCollector


class DummyMultiCityProvider:
    name = "dummy"

    def __init__(self) -> None:
        self.calls: list[int | None] = []

    async def search_multi_city(
        self,
        legs: list[dict[str, object]],
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        self.calls.append(max_stops)
        if max_stops in (1, 2):
            return []
        return [
            ProviderResult(
                price=829.0,
                currency=currency,
                airline="Icelandair / Lufthansa",
                deep_link="",
                provider=self.name,
                stops=0,
                duration_minutes=900,
                raw_data={},
            )
        ]


class DummyOneWayProvider:
    name = "dummy-one-way"

    def __init__(self) -> None:
        self.calls: list[int | None] = []

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
        self.calls.append(max_stops)
        if max_stops == 1:
            return []
        if max_stops == 2:
            return [
                ProviderResult(
                    price=540.0,
                    currency=currency,
                    airline="LOT",
                    deep_link="",
                    provider=self.name,
                    stops=2,
                    duration_minutes=700,
                    raw_data={},
                )
            ]
        return []


@pytest.mark.asyncio
async def test_multi_city_fallback_prefers_1_then_2_then_direct() -> None:
    collector = PriceCollector(
        session_factory=SimpleNamespace(),
        providers=[],
    )
    provider = DummyMultiCityProvider()

    results, stop_label = await collector._search_multi_city_with_fallback(
        provider=provider,
        origin="YYZ",
        destination="BER",
        depart_date=date(2026, 5, 20),
        return_origin="BUD",
        return_date=date(2026, 5, 31),
        currency="CAD",
    )

    assert provider.calls == [1, 2, 0]
    assert len(results) == 1
    assert results[0].price == 829.0
    assert stop_label == "Direct (1 stop and 2 stop unavailable)"
    assert results[0].raw_data["return_origin"] == "BUD"
    assert results[0].raw_data["return_destination"] == "YYZ"
    assert results[0].raw_data["return_date"] == "2026-05-31"


@pytest.mark.asyncio
async def test_one_way_fallback_prefers_1_then_2_then_direct() -> None:
    collector = PriceCollector(
        session_factory=SimpleNamespace(),
        providers=[],
    )
    provider = DummyOneWayProvider()

    results, stop_label = await collector._search_one_way_with_fallback(
        provider=provider,
        origin="YYZ",
        destination="BER",
        depart_date=date(2026, 5, 20),
        currency="CAD",
    )

    assert provider.calls == [1, 2]
    assert len(results) == 1
    assert results[0].price == 540.0
    assert stop_label == "2 stop (1 stop unavailable)"
    assert results[0].raw_data["stop_result_label"] == "2 stop (1 stop unavailable)"


def test_multi_city_export_uses_itinerary_sheet_shape() -> None:
    group = SimpleNamespace(
        trip_type="multi_city",
        origins=["YYZ"],
        destination_label="Berlin",
        nights=11,
        sheet_name_map={"YYZ": "Toronto Open Jaw"},
    )

    results = [
        SimpleNamespace(
            origin="YYZ",
            destination="BER",
            depart_date=date(2026, 5, 20),
            airline="Icelandair / Lufthansa",
            price=829.0,
            stop_label="1 stop",
            itinerary_data={
                "return_date": "2026-05-31",
                "return_origin": "BUD",
                "outbound_airline": "Icelandair",
                "return_airline": "Lufthansa",
                "stop_result_label": "1 stop",
            },
        ),
        SimpleNamespace(
            origin="YYZ",
            destination="BER",
            depart_date=date(2026, 5, 21),
            airline="Air Canada / LOT",
            price=851.0,
            stop_label="2 stop (1 stop unavailable)",
            itinerary_data={
                "return_date": "2026-06-01",
                "return_origin": "BUD",
                "outbound_airline": "Air Canada",
                "return_airline": "LOT",
                "stop_result_label": "2 stop (1 stop unavailable)",
            },
        ),
    ]

    workbook_bytes = export_route_group(group, results)
    workbook = load_workbook(BytesIO(workbook_bytes))

    assert "Toronto Open Jaw" in workbook.sheetnames
    assert workbook.sheetnames == ["Toronto Open Jaw"]
    assert "Return Leg" not in workbook.sheetnames

    sheet = workbook["Toronto Open Jaw"]
    headers = [sheet.cell(row=1, column=index).value for index in range(1, 8)]
    assert headers == [
        "Date",
        "Ending Date",
        "Dep Airport",
        "Arrivel Airport",
        "Night ",
        "Airline",
        "Flight Price",
    ]
    assert sheet["A2"].value == datetime(2026, 5, 20)
    assert sheet["B2"].value == "2026-05-31"
    assert sheet["D2"].value == "Berlin/BUD"
    assert sheet["E2"].value == 11
    assert sheet["F2"].value == "Icelandair / Lufthansa"
    assert sheet["G2"].value == 829
