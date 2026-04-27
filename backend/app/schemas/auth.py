from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

UserRole = Literal["admin", "user", "employee"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: UserRole = "user"

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name cannot be blank")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: UserRole) -> str:
        return "user" if value == "employee" else value


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_optional_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name cannot be blank")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("role")
    @classmethod
    def normalize_optional_role(cls, value: UserRole | None) -> str | None:
        if value is None:
            return None
        return "user" if value == "employee" else value


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
