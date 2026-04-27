from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    database_status: str
    scheduler_running: bool
    provider_status: dict[str, str]
    demo_mode: bool = False
