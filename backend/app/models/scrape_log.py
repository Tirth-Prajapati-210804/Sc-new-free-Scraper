from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)
    depart_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    offers_found: Mapped[int] = mapped_column(Integer, default=0)
    cheapest_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_scrape_logs_route_group", "route_group_id"),
        Index("ix_scrape_logs_created_at", "created_at"),
    )
