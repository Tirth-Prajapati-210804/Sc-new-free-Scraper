from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.stats import OverviewStats
from app.services.stats_service import get_overview

router = APIRouter(prefix="/stats", tags=["stats"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/overview", response_model=OverviewStats)
async def overview(request: Request, session: _DB, current_user: _Auth) -> OverviewStats:
    registry = request.app.state.provider_registry
    return await get_overview(session, registry, current_user)
