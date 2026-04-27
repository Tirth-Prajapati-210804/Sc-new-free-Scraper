"""Tests for app.services.auth_service — user authentication and management."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.schemas.auth import UserCreate, UserUpdate
from app.services.auth_service import (
    authenticate,
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    issue_login_response,
    update_user,
)


def make_user(
    email: str = "user@example.com",
    password: str = "TestPassword123!",
    role: str = "user",
    is_active: bool = True,
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = email
    user.hashed_password = hash_password(password)
    user.full_name = "Test User"
    user.role = role
    user.is_active = is_active
    return user


def make_settings() -> MagicMock:
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-that-is-32-characters!"
    settings.jwt_algorithm = "HS256"
    settings.jwt_access_token_expire_minutes = 60
    return settings


# ── authenticate ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate_success() -> None:
    user = make_user(email="admin@test.com", password="SecurePass123!")
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    result = await authenticate(session, "admin@test.com", "SecurePass123!")
    assert result is not None
    assert result.email == "admin@test.com"


@pytest.mark.asyncio
async def test_authenticate_wrong_password() -> None:
    user = make_user(password="CorrectPassword1!")
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    result = await authenticate(session, "user@example.com", "WrongPassword1!")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found() -> None:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    result = await authenticate(session, "nobody@example.com", "anything1234")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_inactive_user_rejected() -> None:
    user = make_user(password="MyPassword123!", is_active=False)
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    result = await authenticate(session, "user@example.com", "MyPassword123!")
    assert result is None


# ── issue_login_response ─────────────────────────────────────────────────────

def test_issue_login_response_returns_token() -> None:
    user = make_user()
    settings = make_settings()
    response = issue_login_response(user, settings)
    assert response.access_token
    assert response.token_type == "bearer"
    assert response.expires_in == 3600  # 60 minutes * 60 seconds


# ── create_user ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_success() -> None:
    session = AsyncMock()
    # No existing user
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    data = UserCreate(
        full_name="New User",
        email="new@example.com",
        password="StrongPassword12!",
        role="user",
    )
    user = await create_user(session, data)
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises() -> None:
    session = AsyncMock()
    existing = make_user(email="existing@example.com")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result_mock)

    data = UserCreate(
        full_name="Duplicate User",
        email="existing@example.com",
        password="StrongPassword12!",
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_user(session, data)
    assert exc_info.value.status_code == 409


# ── delete_user ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_user_cannot_delete_self() -> None:
    user_id = uuid.uuid4()
    session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await delete_user(session, user_id, user_id)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_user_not_found_raises() -> None:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc_info:
        await delete_user(session, uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code == 404


# ── update_user ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_not_found_raises() -> None:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    data = UserUpdate(full_name="Updated Name")
    with pytest.raises(HTTPException) as exc_info:
        await update_user(session, uuid.uuid4(), data)
    assert exc_info.value.status_code == 404
