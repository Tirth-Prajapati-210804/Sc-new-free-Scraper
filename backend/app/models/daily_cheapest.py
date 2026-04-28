from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyCheapestPrice(Base):
    __tablename__ = "daily_cheapest_prices"
    __table_args__ = (
        UniqueConstraint(
            "route_group_id",
            "origin",
            "destination",
            "depart_date",
            name="uq_daily_cheapest_per_group",
        ),
        Index("ix_daily_cheapest_route_origin_date", "route_group_id", "origin", "depart_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_groups.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)
    depart_date: Mapped[date] = mapped_column(Date, nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CAD")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
