"""Integration tests for /api/v1/users endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_users_requires_admin(make_auth_client):
    user_client = await make_auth_client(
        email="viewer@example.com",
        password="ViewerPassword123!",
        role="viewer",
    )
    res = await user_client.get("/api/v1/users/")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_users_as_admin(auth_client):
    res = await auth_client.get("/api/v1/users/")
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # at least the admin


@pytest.mark.asyncio
async def test_create_user(auth_client):
    res = await auth_client.post("/api/v1/users/", json={
        "full_name": "New User",
        "email": "newuser@example.com",
        "password": "NewUserPassword1!",
        "role": "user",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_user_duplicate_email(auth_client):
    await auth_client.post("/api/v1/users/", json={
        "full_name": "First",
        "email": "dup@example.com",
        "password": "FirstPassword123!",
    })
    res = await auth_client.post("/api/v1/users/", json={
        "full_name": "Second",
        "email": "dup@example.com",
        "password": "SecondPassword12!",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_user(auth_client):
    create_res = await auth_client.post("/api/v1/users/", json={
        "full_name": "Update Me",
        "email": "updateme@example.com",
        "password": "UpdatePassword12!",
    })
    user_id = create_res.json()["id"]

    res = await auth_client.put(f"/api/v1/users/{user_id}", json={
        "full_name": "Updated Name",
        "role": "admin",
    })
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Name"
    assert res.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_delete_user(auth_client):
    create_res = await auth_client.post("/api/v1/users/", json={
        "full_name": "Delete Me",
        "email": "deleteme@example.com",
        "password": "DeletePassword12!",
    })
    user_id = create_res.json()["id"]

    res = await auth_client.delete(f"/api/v1/users/{user_id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_cannot_delete_self(auth_client):
    me_res = await auth_client.get("/api/v1/auth/me")
    my_id = me_res.json()["id"]
    res = await auth_client.delete(f"/api/v1/users/{my_id}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_user_requires_admin(make_auth_client):
    user_client = await make_auth_client(
        email="regular@example.com",
        password="RegularPassword1!",
        role="user",
    )
    res = await user_client.post("/api/v1/users/", json={
        "full_name": "Unauthorized",
        "email": "unauth@example.com",
        "password": "SomePassword1234!",
    })
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_user_weak_password_rejected(auth_client):
    res = await auth_client.post("/api/v1/users/", json={
        "full_name": "Weak",
        "email": "weak@example.com",
        "password": "short",
    })
    assert res.status_code == 422
