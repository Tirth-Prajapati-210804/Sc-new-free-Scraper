from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter, build_rate_limit_key, unwrap_client_host
from app.core.security import normalize_email
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services.auth_service import authenticate, issue_login_response

router = APIRouter(prefix="/auth", tags=["auth"])

_login_rate_limiter = SlidingWindowRateLimiter()


def _build_client_key(request: Request, email: str) -> str:
    client_ip = unwrap_client_host(
        request.headers.get("x-forwarded-for"),
        fallback=lambda: request.client.host if request.client else "unknown",
    )
    return build_rate_limit_key("login", client_ip, email)


def _check_rate_limit(request: Request, email: str, settings: Settings) -> str:
    rate_key = _build_client_key(request, email)
    retry_after = _login_rate_limiter.retry_after(
        rate_key,
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please wait {retry_after} seconds and try again.",
        )
    return rate_key


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    email = normalize_email(body.email)
    rate_key = _check_rate_limit(request, email, settings)
    user = await authenticate(session, email, body.password)
    if not user:
        _login_rate_limiter.add(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    _login_rate_limiter.reset(rate_key)
    return issue_login_response(user, settings)


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)
