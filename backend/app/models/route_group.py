from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RouteGroup(Base):
    __tablename__ = "route_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_routegroups_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Uniqueness is enforced per-owner via UniqueConstraint(user_id, name) in
    # __table_args__. A column-level unique=True would block User B from reusing
    # a name User A already chose — clearly wrong for a multi-tenant tool.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_label: Mapped[str] = mapped_column(String(100), nullable=False)
    destinations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    origins: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    days_ahead: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    sheet_name_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    special_sheets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    max_stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trip_type: Mapped[str] = mapped_column(String(20), nullable=False, default="one_way")
    # Owner of this route group — NULL for legacy records created before multi-user support.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
