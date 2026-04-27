from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderStat(BaseModel):
    configured: bool
    last_success: datetime | None = None
    success_rate: float | None = None


class OverviewStats(BaseModel):
    active_route_groups: int
    total_prices_collected: int
    total_origins: int
    total_destinations: int
    last_collection_at: datetime | None
    last_collection_status: str | None
    provider_stats: dict[str, ProviderStat]
