from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.route_group import RouteGroup
from app.models.user import User
from app.schemas.daily_price import DailyPriceResponse, PriceTrendPoint
from app.services import route_group_service

router = APIRouter(prefix="/prices", tags=["prices"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]
_IATA_QUERY_PATTERN = r"^[A-Za-z0-9]{2,4}$"
async def _ensure_accessible_group(
    session: AsyncSession,
    route_group_id: uuid.UUID,
) -> None:
    group = await route_group_service.get_by_id(session, route_group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route group not found",
        )


@router.get("/", response_model=list[DailyPriceResponse])
async def list_prices(
    session: _DB,
    current_user: _Auth,
    route_group_id: uuid.UUID | None = Query(default=None),
    origin: str | None = Query(default=None, min_length=2, max_length=4, pattern=_IATA_QUERY_PATTERN),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[DailyPriceResponse]:
    if route_group_id:
        await _ensure_accessible_group(session, route_group_id)

    q = (
        select(DailyCheapestPrice)
        .join(RouteGroup, RouteGroup.id == DailyCheapestPrice.route_group_id)
        .order_by(DailyCheapestPrice.depart_date)
        .offset(offset)
        .limit(limit)
    )
    if route_group_id:
        q = q.where(DailyCheapestPrice.route_group_id == route_group_id)
    if origin:
        q = q.where(DailyCheapestPrice.origin == origin.upper())
    if date_from:
        q = q.where(DailyCheapestPrice.depart_date >= date_from)
    if date_to:
        q = q.where(DailyCheapestPrice.depart_date <= date_to)

    result = await session.execute(q)
    return [DailyPriceResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/trend", response_model=list[PriceTrendPoint])
async def price_trend(
    session: _DB,
    current_user: _Auth,
    origin: str = Query(min_length=2, max_length=4, pattern=_IATA_QUERY_PATTERN),
    destination: str = Query(min_length=2, max_length=4, pattern=_IATA_QUERY_PATTERN),
    route_group_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[PriceTrendPoint]:
    if route_group_id:
        await _ensure_accessible_group(session, route_group_id)

    q = (
        select(DailyCheapestPrice)
        .join(RouteGroup, RouteGroup.id == DailyCheapestPrice.route_group_id)
        .where(
            DailyCheapestPrice.origin == origin.upper(),
            DailyCheapestPrice.destination == destination.upper(),
        )
        .order_by(DailyCheapestPrice.depart_date)
    )
    if route_group_id:
        q = q.where(DailyCheapestPrice.route_group_id == route_group_id)
    if date_from:
        q = q.where(DailyCheapestPrice.depart_date >= date_from)
    if date_to:
        q = q.where(DailyCheapestPrice.depart_date <= date_to)

    result = await session.execute(q)
    return [
        PriceTrendPoint(
            depart_date=p.depart_date,
            price=float(p.price),
            airline=p.airline,
        )
        for p in result.scalars().all()
    ]
