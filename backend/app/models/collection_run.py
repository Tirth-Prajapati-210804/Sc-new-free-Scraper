from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    routes_total: Mapped[int] = mapped_column(Integer, default=0)
    routes_success: Mapped[int] = mapped_column(Integer, default=0)
    routes_failed: Mapped[int] = mapped_column(Integer, default=0)
    dates_scraped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_collection_runs_started_at", "started_at"),
    )
