from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, UserCreate, UserResponse


def test_login_request_valid() -> None:
    req = LoginRequest(email=" USER@example.com ", password="securepassword")
    assert req.email == "user@example.com"


def test_login_request_invalid_email() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="securepassword")


def test_login_request_short_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="short")


def test_user_response_from_orm() -> None:
    class FakeUser:
        id = uuid.uuid4()
        email = "admin@example.com"
        full_name = "Admin User"
        role = "admin"

    response = UserResponse.model_validate(FakeUser())
    assert response.email == "admin@example.com"
    assert response.role == "admin"


def test_user_create_requires_strong_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            full_name="Example User",
            email="user@example.com",
            password="short123",
        )
