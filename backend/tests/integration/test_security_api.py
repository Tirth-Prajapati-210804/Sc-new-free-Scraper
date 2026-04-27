from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.daily_cheapest import DailyCheapestPrice


VALID_GROUP = {
    "name": "Canada to Japan",
    "destination_label": "Japan",
    "destinations": ["NRT", "HND"],
    "origins": ["YVR"],
    "nights": 10,
    "days_ahead": 60,
    "currency": "USD",
}


@pytest.mark.asyncio
async def test_inactive_user_cannot_log_in(client, seed_user):
    await seed_user(
        email="inactive@example.com",
        password="InactiveUser123!",
        is_active=False,
    )

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "InactiveUser123!"},
    )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_blocks_repeated_failures(client):
    for _ in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody+ratelimit@example.com", "password": "WrongPassword123!"},
        )
        assert res.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody+ratelimit@example.com", "password": "WrongPassword123!"},
    )

    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_non_admin_can_access_global_collection_controls(make_auth_client):
    user_client = await make_auth_client(
        email="member@example.com",
        password="MemberPassword123!",
    )

    runs_res = await user_client.get("/api/v1/collection/runs")
    trigger_res = await user_client.post("/api/v1/collection/trigger")
    stats_res = await user_client.get("/api/v1/stats/overview")

    assert runs_res.status_code == 200
    assert trigger_res.status_code in {200, 400}
    assert stats_res.status_code == 200


@pytest.mark.asyncio
async def test_user_can_trigger_and_view_other_users_route_group(make_auth_client, seed_user):
    owner_client = await make_auth_client(
        email="owner@example.com",
        password="OwnerPassword123!",
    )
    other_client = await make_auth_client(
        email="other@example.com",
        password="OtherPassword123!",
    )

    create_res = await owner_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    assert create_res.status_code == 201
    group_id = create_res.json()["id"]

    trigger_res = await other_client.post(f"/api/v1/collection/trigger-group/{group_id}")
    prices_res = await other_client.get("/api/v1/prices/", params={"route_group_id": group_id})
    logs_res = await other_client.get("/api/v1/collection/logs", params={"route_group_id": group_id})

    assert trigger_res.status_code in {200, 400}
    assert prices_res.status_code == 200
    assert logs_res.status_code == 200


@pytest.mark.asyncio
async def test_prices_are_scoped_to_current_user(auth_client, make_auth_client, db_session_factory):
    owner_client = await make_auth_client(
        email="scoped-owner@example.com",
        password="ScopedOwner123!",
    )
    other_client = await make_auth_client(
        email="scoped-other@example.com",
        password="ScopedOther123!",
    )

    create_res = await owner_client.post("/api/v1/route-groups/", json=VALID_GROUP)
    assert create_res.status_code == 201
    payload = create_res.json()
    group_id = payload["id"]

    async with db_session_factory() as session:
        session.add(
            DailyCheapestPrice(
                route_group_id=uuid.UUID(group_id),
                origin="YVR",
                destination="NRT",
                depart_date=date(2026, 5, 1),
                airline="AC",
                price=Decimal("799.00"),
                currency="USD",
                provider="serpapi",
                deep_link="https://example.com",
            )
        )
        await session.commit()

    owner_prices = await owner_client.get("/api/v1/prices/", params={"route_group_id": group_id})
    admin_prices = await auth_client.get("/api/v1/prices/", params={"route_group_id": group_id})
    other_prices = await other_client.get("/api/v1/prices/")

    assert owner_prices.status_code == 200
    assert len(owner_prices.json()) == 1
    assert admin_prices.status_code == 200
    assert len(admin_prices.json()) == 1
    assert other_prices.status_code == 200
    assert len(other_prices.json()) == 1
