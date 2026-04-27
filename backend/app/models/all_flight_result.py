"""
AllFlightResult model — every flight offer returned by every provider.

Unlike daily_cheapest_prices (which keeps only the single cheapest fare per
route/date), this table keeps ALL results from all providers so users can
see the full picture: multiple airlines, price tiers, stop counts, etc.

Insert strategy: replace-on-collect. Before inserting new results for a
given (route_group_id, origin, destination, depart_date), the collector
deletes any existing rows for that combination. This ensures the table
always reflects the most recent collection rather than growing unboundedly.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AllFlightResult(Base):
    __tablename__ = "all_flight_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK to route_groups — CASCADE delete so records vanish when the group is deleted
    route_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    destination: Mapped[str] = mapped_column(String(10), nullable=False)
    depart_date: Mapped[date] = mapped_column(Date, nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CAD")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Fast lookup when building the export: all results for a group, sorted by date
        Index("ix_all_flight_results_group_route_date", "route_group_id", "origin", "destination", "depart_date"),
    )
