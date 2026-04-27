from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import UserCreate, UserListResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


def _require_admin(current_user: _Auth) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.get("/", response_model=list[UserListResponse])
async def list_users(session: _DB, current_user: _Auth) -> list[UserListResponse]:
    _require_admin(current_user)
    users = await auth_service.list_users(session)
    return [UserListResponse.model_validate(u) for u in users]


@router.post("/", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, session: _DB, current_user: _Auth) -> UserListResponse:
    _require_admin(current_user)
    user = await auth_service.create_user(session, body)
    return UserListResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, session: _DB, current_user: _Auth
) -> UserListResponse:
    _require_admin(current_user)
    user = await auth_service.update_user(session, user_id, body)
    return UserListResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: _DB, current_user: _Auth) -> None:
    _require_admin(current_user)
    await auth_service.delete_user(session, user_id, current_user.id)
