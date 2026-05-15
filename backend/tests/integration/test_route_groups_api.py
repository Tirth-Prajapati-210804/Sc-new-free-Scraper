"""Integration tests for the /api/v1/route-groups endpoints."""
from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import func, select


VALID_GROUP = {
    "name": "Canada to Vietnam",
    "destination_label": "Vietnam",
    "destinations": ["SGN", "HAN"],
    "origins": ["YVR", "YYZ"],
    "nights": 10,
    "days_ahead": 90,
}


@pytest.mark.asyncio
async def test_export_route_group_returns_excel_file(auth_client, db_session_factory):
    from datetime import date
    from decimal import Decimal
    from uuid import UUID

    from app.models.all_flight_result import AllFlightResult

    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        session.add(
            AllFlightResult(
                route_group_id=UUID(group_id),
                origin="YVR",
                destination="SGN",
                depart_date=date(2026, 5, 1),
                airline="Air Canada",
                price=799.0,
                currency="USD",
                provider="demo",
                deep_link="https://example.com",
            )
        )
        await session.commit()

    res = await auth_client.get(f"/api/v1/route-groups/{group_id}/export")
    assert res.status_code == 200
    assert (
        res.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert res.content.startswith(b"PK")


@pytest.mark.asyncio
async def test_list_route_group_results_returns_itinerary_data(auth_client, db_session_factory):
    from datetime import date

    from app.models.all_flight_result import AllFlightResult

    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    async with db_session_factory() as session:
        session.add(
            AllFlightResult(
                route_group_id=UUID(group_id),
                origin="YVR",
                destination="SGN",
                depart_date=date(2026, 5, 1),
                airline="Cathay Pacific",
                price=991.0,
                currency="USD",
                provider="scrapingbee",
                deep_link="https://example.com/book/1",
                stops=1,
                duration_minutes=1242,
                itinerary_data={
                    "trip_type": "multi_city",
                    "price_text": "$991",
                    "legs": [
                        {"time_text": "1:25 am - 3:00 pm+1", "route_text": "YVR-DPS"},
                        {"time_text": "6:00 pm - 9:50 pm", "route_text": "SIN-YVR"},
                    ],
                },
            )
        )
        await session.commit()

    res = await auth_client.get(
        f"/api/v1/route-groups/{group_id}/results",
        params={"depart_date": "2026-05-01", "origin": "yvr"},
    )

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["airline"] == "Cathay Pacific"
    assert data[0]["price"] == 991.0
    assert data[0]["itinerary_data"]["price_text"] == "$991"
    assert data[0]["itinerary_data"]["legs"][0]["time_text"] == "1:25 am - 3:00 pm+1"


@pytest.mark.asyncio
async def test_create_route_group(auth_client):
    res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Canada to Vietnam"
    assert data["destinations"] == ["SGN", "HAN"]
    assert data["origins"] == ["YVR", "YYZ"]
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_route_groups(auth_client):
    await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    res = await auth_client.get("/api/v1/route-groups/")
    assert res.status_code == 200
    groups = res.json()
    assert len(groups) == 1
    assert groups[0]["name"] == "Canada to Vietnam"


@pytest.mark.asyncio
async def test_get_route_group_by_id(auth_client):
    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    res = await auth_client.get(f"/api/v1/route-groups/{group_id}")
    assert res.status_code == 200
    assert res.json()["id"] == group_id


@pytest.mark.asyncio
async def test_get_route_group_not_found(auth_client):
    res = await auth_client.get("/api/v1/route-groups/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_route_group(auth_client):
    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    res = await auth_client.put(
        f"/api/v1/route-groups/{group_id}",
        json={"name": "Updated Name", "nights": 14},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Name"
    assert data["nights"] == 14
    # Other fields unchanged
    assert data["destinations"] == ["SGN", "HAN"]


@pytest.mark.asyncio
async def test_delete_route_group(auth_client):
    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    del_res = await auth_client.delete(f"/api/v1/route-groups/{group_id}")
    assert del_res.status_code == 204

    get_res = await auth_client.get(f"/api/v1/route-groups/{group_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_progress_returns_zero_for_new_group(auth_client):
    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]

    res = await auth_client.get(f"/api/v1/route-groups/{group_id}/progress")
    assert res.status_code == 200
    data = res.json()
    assert data["dates_with_data"] == 0
    assert data["coverage_percent"] == 0.0
    assert data["scraped_dates"] == []
    # total = origins x destinations x (today + days_ahead inclusive)
    assert data["total_dates"] == 2 * 2 * 91


@pytest.mark.asyncio
async def test_create_route_group_requires_auth(client):
    res = await client.post("/api/v1/route-groups/", json=VALID_GROUP)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_invalid_iata_code_rejected(auth_client):
    bad = {**VALID_GROUP, "origins": ["INVALID_CODE"]}
    res = await auth_client.post("/api/v1/route-groups/", json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_location_suggestions_returns_matches(auth_client):
    res = await auth_client.get("/api/v1/route-groups/location-suggestions", params={"q": "ca"})
    assert res.status_code == 200
    data = res.json()
    assert any(item["label"] == "Canada" for item in data)


@pytest.mark.asyncio
async def test_update_route_group_clears_stale_collection_data(auth_client, db_session_factory):
    from app.models.all_flight_result import AllFlightResult
    from app.models.daily_cheapest import DailyCheapestPrice
    from app.models.scrape_log import ScrapeLog

    create_res = await auth_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    group_id = create_res.json()["id"]
    group_uuid = UUID(group_id)

    async with db_session_factory() as session:
        session.add(
            DailyCheapestPrice(
                route_group_id=group_uuid,
                origin="YVR",
                destination="SGN",
                depart_date=date(2026, 5, 1),
                airline="Air Canada",
                price=799.0,
                currency="USD",
                provider="searchapi",
            )
        )
        session.add(
            AllFlightResult(
                route_group_id=group_uuid,
                origin="YVR",
                destination="SGN",
                depart_date=date(2026, 5, 1),
                airline="Air Canada",
                price=799.0,
                currency="USD",
                provider="searchapi",
                deep_link="https://example.com",
            )
        )
        session.add(
            ScrapeLog(
                route_group_id=group_uuid,
                origin="YVR",
                destination="SGN",
                depart_date=date(2026, 5, 1),
                provider="searchapi",
                status="success",
                offers_found=1,
                cheapest_price=799.0,
            )
        )
        await session.commit()

    res = await auth_client.put(
        f"/api/v1/route-groups/{group_id}",
        json={"destinations": ["NRT"]},
    )
    assert res.status_code == 200

    async with db_session_factory() as session:
        daily_count = (
            await session.execute(
                select(func.count()).select_from(DailyCheapestPrice).where(
                    DailyCheapestPrice.route_group_id == group_uuid
                )
            )
        ).scalar_one()
        all_results_count = (
            await session.execute(
                select(func.count()).select_from(AllFlightResult).where(
                    AllFlightResult.route_group_id == group_uuid
                )
            )
        ).scalar_one()
        scrape_log_count = (
            await session.execute(
                select(func.count()).select_from(ScrapeLog).where(
                    ScrapeLog.route_group_id == group_uuid
                )
            )
        ).scalar_one()

    assert daily_count == 0
    assert all_results_count == 0
    assert scrape_log_count == 0
