from __future__ import annotations

import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import SlidingWindowRateLimiter, build_rate_limit_key, unwrap_client_host
from app.db.session import get_db_session
from app.models.collection_run import CollectionRun
from app.models.route_group import RouteGroup
from app.models.scrape_log import ScrapeLog
from app.models.user import User
from app.services import route_group_service

router = APIRouter(prefix="/collection", tags=["collection"])

_scrape_rate_limiter = SlidingWindowRateLimiter()
_IATA_QUERY_PATTERN = r"^[A-Za-z0-9]{2,4}$"


def _enforce_scrape_rate_limit(request: Request, user: User, scope: str) -> None:
    settings = request.app.state.settings
    client_ip = unwrap_client_host(
        request.headers.get("x-forwarded-for"),
        fallback=lambda: request.client.host if request.client else "unknown",
    )
    key = build_rate_limit_key("scrape", scope, client_ip, user.id)
    retry_after = _scrape_rate_limiter.hit(
        key,
        limit=settings.scrape_rate_limit_attempts,
        window_seconds=settings.scrape_rate_limit_window_seconds,
    )
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Collection endpoint is rate limited. Please wait {retry_after} seconds and try again.",
        )


def _provider_unavailable_detail(registry) -> str:
    provider_status = registry.status()
    status_messages = {
        "quota_exhausted": "quota is exhausted. Add more credits or quota before triggering collection again.",
        "auth_error": "authentication failed. Check the configured credentials before triggering collection again.",
        "rate_limited": "is temporarily rate limited. Wait for the cooldown and try again.",
        "cooldown": "is temporarily unavailable after recent provider failures. Check provider status and collection logs.",
        "error": "is temporarily unavailable after recent provider failures. Check provider status and collection logs.",
        "provider_error": "is temporarily unavailable after recent provider failures. Check provider status and collection logs.",
    }

    for provider_name, provider_state in provider_status.items():
        if provider_state in status_messages:
            label = provider_name.replace("_", " ").title()
            return f"{label} {status_messages[provider_state]}"

    return (
        "No flight data provider is configured. Add SCRAPINGBEE_API_KEY or "
        "SCRAPINGBEE_API_KEYS to your .env file, or enable DEMO_MODE=true to "
        "use demo data."
    )


async def _get_accessible_group(
    session: AsyncSession,
    group_id: uuid.UUID,
) -> RouteGroup:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route group not found")
    return group


@router.get("/status")
async def collection_status(
    request: Request,
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    scheduler = request.app.state.scheduler
    result: dict = {
        "is_collecting": scheduler.is_collecting,
        "scheduler_running": scheduler.is_running,
    }
    if scheduler.is_collecting:
        result["progress"] = scheduler.progress
    return result


@router.post("/trigger")
async def trigger_collection(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    _enforce_scrape_rate_limit(request, current_user, "all")
    scheduler = request.app.state.scheduler
    if scheduler.is_collecting:
        return {"status": "already_running"}
    registry = request.app.state.provider_registry
    if not registry.get_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_provider_unavailable_detail(registry),
        )
    scheduler.start_collection_task()
    return {"status": "triggered"}


@router.post("/stop")
async def stop_collection(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    _enforce_scrape_rate_limit(request, current_user, "stop")
    scheduler = request.app.state.scheduler
    if not scheduler.is_collecting:
        return {"status": "not_running"}
    scheduler.request_stop()
    return {"status": "stop_requested"}


@router.post("/trigger-group/{group_id}")
async def trigger_group(
    group_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    _enforce_scrape_rate_limit(request, current_user, f"group:{group_id}")
    await _get_accessible_group(session, group_id)
    scheduler = request.app.state.scheduler
    registry = request.app.state.provider_registry
    if not registry.get_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_provider_unavailable_detail(registry),
        )
    scheduler.start_single_group_task(group_id)
    return {"status": "triggered", "group_id": str(group_id)}


@router.post("/trigger-group/{group_id}/date/{target_date}")
async def trigger_group_date(
    group_id: uuid.UUID,
    target_date: date_type,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    _enforce_scrape_rate_limit(request, current_user, f"group-date:{group_id}:{target_date}")
    await _get_accessible_group(session, group_id)
    scheduler = request.app.state.scheduler
    registry = request.app.state.provider_registry
    if not registry.get_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_provider_unavailable_detail(registry),
        )
    scheduler.start_single_group_task(group_id, [target_date])
    return {"status": "triggered", "group_id": str(group_id), "date": str(target_date)}


@router.get("/runs")
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    result = await session.execute(
        select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "routes_total": r.routes_total,
            "routes_success": r.routes_success,
            "routes_failed": r.routes_failed,
            "dates_scraped": r.dates_scraped,
            "errors": r.errors,
        }
        for r in runs
    ]


@router.get("/logs")
async def list_logs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    route_group_id: uuid.UUID | None = Query(default=None),
    origin: str | None = Query(default=None, min_length=2, max_length=4, pattern=_IATA_QUERY_PATTERN),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    if route_group_id:
        await _get_accessible_group(session, route_group_id)

    q = select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(limit)

    if route_group_id:
        q = q.where(ScrapeLog.route_group_id == route_group_id)
    if origin:
        q = q.where(ScrapeLog.origin == origin.upper())

    result = await session.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": str(lg.id),
            "origin": lg.origin,
            "destination": lg.destination,
            "depart_date": lg.depart_date.isoformat(),
            "provider": lg.provider,
            "status": lg.status,
            "offers_found": lg.offers_found,
            "cheapest_price": float(lg.cheapest_price) if lg.cheapest_price else None,
            "error_message": lg.error_message,
            "duration_ms": lg.duration_ms,
            "created_at": lg.created_at.isoformat() if lg.created_at else None,
        }
        for lg in logs
    ]
