from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.route_group import RouteGroupCreate


def test_route_group_create_normalizes_codes_and_currency() -> None:
    payload = RouteGroupCreate(
        name=" Canada to Japan ",
        destination_label=" Japan ",
        destinations=["nrt", "hnd"],
        origins=["yvr"],
        nights=10,
        days_ahead=30,
        currency="usd",
    )

    assert payload.name == "Canada to Japan"
    assert payload.destination_label == "Japan"
    assert payload.destinations == ["NRT", "HND"]
    assert payload.origins == ["YVR"]
    assert payload.currency == "USD"


def test_route_group_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        RouteGroupCreate(
            name="Bad currency",
            destination_label="Japan",
            destinations=["NRT"],
            origins=["YVR"],
            nights=7,
            days_ahead=30,
            currency="USDX",
        )


def test_route_group_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError):
        RouteGroupCreate(
            name="Canada to Japan",
            destination_label="Japan",
            destinations=["NRT"],
            origins=["YVR"],
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 1),
        )
