from __future__ import annotations

import re
import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.all_flight_result import AllFlightResult
from app.models.user import User
from app.schemas.location import LocationSuggestion
from app.schemas.route_group import (
    RouteGroupCreate,
    RouteGroupProgress,
    RouteGroupResponse,
    RouteGroupUpdate,
)
from app.services import export_service, route_group_service
from app.utils.location_resolver import search_location_suggestions

router = APIRouter(prefix="/route-groups", tags=["route-groups"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/location-suggestions", response_model=list[LocationSuggestion])
async def location_suggestions(
    q: str,
    current_user: _Auth,
    limit: int = 8,
) -> list[LocationSuggestion]:
    _ = current_user
    safe_limit = max(1, min(limit, 12))
    return [LocationSuggestion.model_validate(item) for item in search_location_suggestions(q, limit=safe_limit)]


@router.get("/", response_model=list[RouteGroupResponse])
async def list_groups(session: _DB, current_user: _Auth, active_only: bool = True) -> list[RouteGroupResponse]:
    groups = await route_group_service.list_all(session, active_only=active_only)
    return [RouteGroupResponse.model_validate(g) for g in groups]


@router.post("/", response_model=RouteGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(body: RouteGroupCreate, session: _DB, current_user: _Auth) -> RouteGroupResponse:
    group = await route_group_service.create(session, body, owner_id=current_user.id)
    return RouteGroupResponse.model_validate(group)


@router.get("/{group_id}", response_model=RouteGroupResponse)
async def get_group(group_id: uuid.UUID, session: _DB, current_user: _Auth) -> RouteGroupResponse:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")
    return RouteGroupResponse.model_validate(group)


@router.put("/{group_id}", response_model=RouteGroupResponse)
async def update_group(
    group_id: uuid.UUID, body: RouteGroupUpdate, session: _DB, current_user: _Auth
) -> RouteGroupResponse:
    group = await route_group_service.update(session, group_id, body)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")
    return RouteGroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, session: _DB, current_user: _Auth) -> None:
    deleted = await route_group_service.delete(session, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Route group not found")


@router.get("/{group_id}/export")
async def export_group(group_id: uuid.UUID, session: _DB, current_user: _Auth) -> StreamingResponse:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")

    all_results_result = await session.execute(
        select(AllFlightResult).where(AllFlightResult.route_group_id == group_id)
    )
    all_results = list(all_results_result.scalars().all())

    excel_bytes = export_service.export_route_group(group, all_results)
    # Sanitize filename: strip dangerous chars, quotes, newlines, and limit length
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", group.name).strip("._") or "route-group"
    safe_name = safe_name.replace('"', "").replace("'", "")[:100]
    filename = f"{safe_name}.xlsx"

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"},
    )


@router.get("/{group_id}/results")
async def list_group_results(
    group_id: uuid.UUID,
    session: _DB,
    current_user: _Auth,
    depart_date: date_type | None = Query(default=None),
    origin: str | None = Query(default=None, min_length=2, max_length=4),
    destination: str | None = Query(default=None, min_length=2, max_length=4),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")

    q = select(AllFlightResult).where(AllFlightResult.route_group_id == group_id)

    if depart_date:
        q = q.where(AllFlightResult.depart_date == depart_date)
    if origin:
        q = q.where(AllFlightResult.origin == origin.upper())
    if destination:
        q = q.where(AllFlightResult.destination == destination.upper())

    q = q.order_by(
        AllFlightResult.depart_date.asc(),
        AllFlightResult.price.asc(),
        AllFlightResult.scraped_at.asc(),
    ).limit(limit)

    result = await session.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "origin": row.origin,
            "destination": row.destination,
            "depart_date": row.depart_date.isoformat(),
            "airline": row.airline,
            "price": row.price,
            "currency": row.currency,
            "provider": row.provider,
            "deep_link": row.deep_link,
            "stops": row.stops,
            "stop_label": row.stop_label,
            "duration_minutes": row.duration_minutes,
            "itinerary_data": row.itinerary_data,
            "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None,
        }
        for row in rows
    ]


@router.get("/{group_id}/progress", response_model=RouteGroupProgress)
async def get_progress(group_id: uuid.UUID, session: _DB, current_user: _Auth) -> RouteGroupProgress:
    # Verify access first
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")
    progress = await route_group_service.get_progress(session, group_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Route group not found")
    return progress
