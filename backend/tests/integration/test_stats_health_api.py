"""Integration tests for /api/v1/stats and health endpoints."""
from __future__ import annotations

import pytest


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_overview_is_available_to_authenticated_users(make_auth_client):
    user_client = await make_auth_client(
        email="stats-user@example.com",
        password="StatsUserPassword1!",
        role="user",
    )
    res = await user_client.get("/api/v1/stats/overview")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_stats_overview_as_admin(auth_client):
    res = await auth_client.get("/api/v1/stats/overview")
    assert res.status_code == 200
    data = res.json()
    assert "active_route_groups" in data
    assert "total_prices_collected" in data
    assert "total_origins" in data
    assert "total_destinations" in data
    assert "provider_stats" in data


@pytest.mark.asyncio
async def test_stats_overview_reflects_route_group(auth_client):
    # Create a route group
    await auth_client.post("/api/v1/route-groups/", json={
        "name": "Stats Test Group",
        "destination_label": "Japan",
        "destinations": ["NRT"],
        "origins": ["YVR"],
        "nights": 7,
        "days_ahead": 30,
    })

    res = await auth_client.get("/api/v1/stats/overview")
    assert res.status_code == 200
    assert res.json()["active_route_groups"] >= 1


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_live(client):
    res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client):
    res = await client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("ok", "degraded")
    assert "database_status" in data
    assert "scheduler_running" in data


@pytest.mark.asyncio
async def test_health_ready_includes_provider_status(client):
    res = await client.get("/health/ready")
    data = res.json()
    assert "provider_status" in data
    assert isinstance(data["provider_status"], dict)
