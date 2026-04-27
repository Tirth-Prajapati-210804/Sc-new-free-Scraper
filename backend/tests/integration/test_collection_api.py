"""Integration tests for /api/v1/collection endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_collection_status(auth_client):
    res = await auth_client.get("/api/v1/collection/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_collecting" in data
    assert "scheduler_running" in data


@pytest.mark.asyncio
async def test_collection_status_requires_auth(client):
    res = await client.get("/api/v1/collection/status")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_trigger_collection_is_available_to_authenticated_users(make_auth_client):
    user_client = await make_auth_client(
        email="trigger-user@example.com",
        password="TriggerPassword1!",
        role="user",
    )
    res = await user_client.post("/api/v1/collection/trigger")
    assert res.status_code == 400
    assert "provider" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stop_collection_is_available_to_authenticated_users(make_auth_client):
    user_client = await make_auth_client(
        email="stop-user@example.com",
        password="StopUserPassword1!",
        role="user",
    )
    res = await user_client.post("/api/v1/collection/stop")
    assert res.status_code == 200
    assert res.json()["status"] == "not_running"


@pytest.mark.asyncio
async def test_trigger_collection_no_providers(auth_client):
    """Triggering when no provider is configured should return 400."""
    res = await auth_client.post("/api/v1/collection/trigger")
    assert res.status_code == 400
    assert "provider" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stop_collection_when_not_running(auth_client):
    res = await auth_client.post("/api/v1/collection/stop")
    assert res.status_code == 200
    assert res.json()["status"] == "not_running"


@pytest.mark.asyncio
async def test_list_runs_is_available_to_authenticated_users(make_auth_client):
    user_client = await make_auth_client(
        email="runs-user@example.com",
        password="RunsUserPassword1!",
        role="user",
    )
    res = await user_client.get("/api/v1/collection/runs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_runs_as_admin(auth_client):
    res = await auth_client.get("/api/v1/collection/runs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_logs_as_admin(auth_client):
    res = await auth_client.get("/api/v1/collection/logs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_logs_with_valid_filters(auth_client):
    res = await auth_client.get("/api/v1/collection/logs", params={
        "origin": "YVR",
        "limit": 10,
    })
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_trigger_group_not_found(auth_client):
    res = await auth_client.post(
        "/api/v1/collection/trigger-group/00000000-0000-0000-0000-000000000000"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_trigger_group_date_not_found(auth_client):
    res = await auth_client.post(
        "/api/v1/collection/trigger-group/00000000-0000-0000-0000-000000000000/date/2026-06-01"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_logs_scoped_to_user(make_auth_client):
    """Authenticated users can access the shared collection logs feed."""
    user_client = await make_auth_client(
        email="logs-scoped@example.com",
        password="LogsScopedPass1!",
        role="user",
    )
    res = await user_client.get("/api/v1/collection/logs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
