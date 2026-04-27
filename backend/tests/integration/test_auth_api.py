"""Integration tests for the /api/v1/auth endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "CIAdminPassword1!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@example.com"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "anything"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_current_user(auth_client):
    res = await auth_client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_get_me_requires_auth(client):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 401
