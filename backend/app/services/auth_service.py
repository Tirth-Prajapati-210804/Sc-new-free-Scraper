from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, normalize_email, verify_password
from app.models.user import User
from app.schemas.auth import LoginResponse, UserCreate, UserUpdate, UserResponse

_DUMMY_PASSWORD_HASH = hash_password("FlightTrackerDummyPassword1!")


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return user



async def ensure_default_admin(session: AsyncSession, settings: Settings) -> None:
    existing = await get_user_by_email(session, settings.admin_email)
    if existing:
        return
    admin = User(
        email=normalize_email(settings.admin_email),
        hashed_password=hash_password(settings.admin_password),
        full_name=settings.admin_full_name,
        role="admin",
        is_active=True,
    )
    session.add(admin)
    await session.commit()


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=normalize_email(data.email),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.email is not None:
        conflict = await get_user_by_email(session, data.email)
        if conflict and conflict.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user.email = normalize_email(data.email)
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(
    session: AsyncSession, user_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    if user_id == current_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(User).where(User.id == user_id))
    await session.commit()


def issue_login_response(user: User, settings: Settings) -> LoginResponse:
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expire_minutes,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )
