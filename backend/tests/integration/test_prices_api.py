"""Integration tests for /api/v1/prices endpoints."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.daily_cheapest import DailyCheapestPrice


VALID_GROUP = {
    "name": "Price Test Group",
    "destination_label": "Japan",
    "destinations": ["NRT", "HND"],
    "origins": ["YVR"],
    "nights": 10,
    "days_ahead": 60,
    "currency": "USD",
}


@pytest.mark.asyncio
async def test_list_prices_empty(auth_client):
    res = await auth_client.get("/api/v1/prices/")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_prices_requires_auth(client):
    res = await client.get("/api/v1/prices/")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_prices_with_data(auth_client, db_session_factory):
    # Create a route group first
    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    assert create_res.status_code == 201
    group_id = create_res.json()["id"]

    # Seed a price directly
    async with db_session_factory() as session:
        session.add(DailyCheapestPrice(
            route_group_id=uuid.UUID(group_id),
            origin="YVR",
            destination="NRT",
            depart_date=date(2026, 6, 1),
            airline="AC",
            price=Decimal("999.00"),
            currency="USD",
            provider="serpapi",
            deep_link="https://example.com",
        ))
        await session.commit()

    res = await auth_client.get("/api/v1/prices/", params={"route_group_id": group_id})
    assert res.status_code == 200
    prices = res.json()
    assert len(prices) == 1
    assert prices[0]["origin"] == "YVR"
    assert prices[0]["destination"] == "NRT"
    assert prices[0]["price"] == 999.0


@pytest.mark.asyncio
async def test_list_prices_filter_by_origin(auth_client, db_session_factory):
    create_res = await auth_client.post("/api/v1/route-groups/", json={
        **VALID_GROUP, "name": "Origin Filter Test"
    })
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        for origin in ["YVR", "YYZ"]:
            session.add(DailyCheapestPrice(
                route_group_id=uuid.UUID(group_id),
                origin=origin,
                destination="NRT",
                depart_date=date(2026, 6, 15),
                airline="AC",
                price=Decimal("800.00"),
                currency="USD",
                provider="serpapi",
            ))
        await session.commit()

    res = await auth_client.get("/api/v1/prices/", params={
        "route_group_id": group_id,
        "origin": "YVR",
    })
    assert res.status_code == 200
    prices = res.json()
    assert all(p["origin"] == "YVR" for p in prices)


@pytest.mark.asyncio
async def test_list_prices_filter_by_date_range(auth_client, db_session_factory):
    create_res = await auth_client.post("/api/v1/route-groups/", json={
        **VALID_GROUP, "name": "Date Filter Test"
    })
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        for day in [1, 15, 30]:
            session.add(DailyCheapestPrice(
                route_group_id=uuid.UUID(group_id),
                origin="YVR",
                destination="NRT",
                depart_date=date(2026, 6, day),
                airline="AC",
                price=Decimal("700.00"),
                currency="USD",
                provider="serpapi",
            ))
        await session.commit()

    res = await auth_client.get("/api/v1/prices/", params={
        "route_group_id": group_id,
        "date_from": "2026-06-10",
        "date_to": "2026-06-20",
    })
    assert res.status_code == 200
    prices = res.json()
    assert len(prices) == 1
    assert prices[0]["depart_date"] == "2026-06-15"


@pytest.mark.asyncio
async def test_list_prices_pagination(auth_client, db_session_factory):
    create_res = await auth_client.post("/api/v1/route-groups/", json={
        **VALID_GROUP, "name": "Pagination Test"
    })
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        for day in range(1, 6):
            session.add(DailyCheapestPrice(
                route_group_id=uuid.UUID(group_id),
                origin="YVR",
                destination="NRT",
                depart_date=date(2026, 7, day),
                airline="AC",
                price=Decimal("600.00"),
                currency="USD",
                provider="serpapi",
            ))
        await session.commit()

    res = await auth_client.get("/api/v1/prices/", params={
        "route_group_id": group_id,
        "limit": 2,
        "offset": 0,
    })
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_price_trend_requires_auth(client):
    res = await client.get("/api/v1/prices/trend", params={
        "origin": "YVR",
        "destination": "NRT",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_price_trend_empty(auth_client):
    res = await auth_client.get("/api/v1/prices/trend", params={
        "origin": "YVR",
        "destination": "NRT",
    })
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_price_trend_with_data(auth_client, db_session_factory):
    create_res = await auth_client.post("/api/v1/route-groups/", json={
        **VALID_GROUP, "name": "Trend Test"
    })
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        for day, price in [(1, 800), (2, 750), (3, 900)]:
            session.add(DailyCheapestPrice(
                route_group_id=uuid.UUID(group_id),
                origin="YVR",
                destination="NRT",
                depart_date=date(2026, 8, day),
                airline="AC",
                price=Decimal(str(price)),
                currency="USD",
                provider="serpapi",
            ))
        await session.commit()

    res = await auth_client.get("/api/v1/prices/trend", params={
        "origin": "YVR",
        "destination": "NRT",
    })
    assert res.status_code == 200
    trend = res.json()
    assert len(trend) == 3
    assert trend[0]["price"] == 800.0
    assert trend[1]["price"] == 750.0


@pytest.mark.asyncio
async def test_price_trend_invalid_origin_rejected(auth_client):
    res = await auth_client.get("/api/v1/prices/trend", params={
        "origin": "INVALID_LONG_CODE",
        "destination": "NRT",
    })
    assert res.status_code == 422
