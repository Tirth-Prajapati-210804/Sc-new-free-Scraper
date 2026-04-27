from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
