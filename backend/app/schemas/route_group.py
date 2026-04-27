from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IATA_PATTERN = r"^[A-Z0-9]{2,4}$"
_CURRENCY_PATTERN = r"^[A-Z]{3}$"
_ALLOWED_TRIP_TYPES = {"one_way", "round_trip", "multi_city"}


def _normalize_iata_codes(v: object) -> list[str] | object:
    import re

    if isinstance(v, list):
        codes = [str(code).strip().upper() for code in v]
        for code in codes:
            if not re.match(_IATA_PATTERN, code):
                raise ValueError(
                    f"'{code}' is not a valid IATA airport code. "
                    "Codes must be 2-4 uppercase letters or digits (e.g. YVR, DPS, TYO)."
                )
        return codes
    return v


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Value cannot be blank")
    return normalized


def _normalize_trip_type(value: object) -> str:
    trip = str(value).strip().lower()

    if trip not in _ALLOWED_TRIP_TYPES:
        raise ValueError(
            "trip_type must be one of: one_way, round_trip, multi_city"
        )

    return trip


class SpecialSheetConfig(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    origin: str = Field(min_length=2, max_length=4, pattern=_IATA_PATTERN)
    destination_label: str = Field(min_length=1, max_length=100)
    destinations: list[str] = Field(min_length=1)
    columns: int = Field(default=4, ge=1, le=12)

    @field_validator("name", "destination_label")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("origin", mode="before")
    @classmethod
    def normalize_origin(cls, value: object) -> str:
        normalized = _normalize_iata_codes([value])
        return normalized[0] if isinstance(normalized, list) else str(value)

    @field_validator("destinations", mode="before")
    @classmethod
    def uppercase_destinations(cls, value: object) -> list[str]:
        normalized = _normalize_iata_codes(value)
        return normalized if isinstance(normalized, list) else []


class RouteGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    destination_label: str = Field(min_length=1, max_length=100)
    destinations: list[str] = Field(min_length=1)
    origins: list[str] = Field(min_length=1)
    nights: int = Field(ge=1, le=90, default=12)
    days_ahead: int = Field(ge=1, le=730, default=365)
    sheet_name_map: dict[str, str] = Field(default_factory=dict)
    special_sheets: list[SpecialSheetConfig] = Field(default_factory=list)
    currency: str = Field(default="USD", pattern=_CURRENCY_PATTERN)
    max_stops: int | None = Field(default=None, ge=0, le=3)
    start_date: date | None = None
    end_date: date | None = None
    trip_type: str = Field(default="one_way")

    @field_validator("name", "destination_label")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str]:
        normalized = _normalize_iata_codes(v)
        return normalized if isinstance(normalized, list) else []

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, value: object) -> str:
        return str(value).strip().upper()

    @field_validator("sheet_name_map")
    @classmethod
    def validate_sheet_name_map(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(key).strip().upper(): _normalize_text(str(sheet)) for key, sheet in value.items()}

    @field_validator("trip_type", mode="before")
    @classmethod
    def validate_trip_type(cls, value: object) -> str:
        if value is None:
            return None
        return _normalize_trip_type(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "RouteGroupCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.trip_type == "multi_city":
            if not self.special_sheets:
                raise ValueError("multi_city requires a return leg configuration")
            if len(self.special_sheets) != 1:
                raise ValueError("multi_city supports exactly one return-leg configuration")
        return self


class RouteGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    destination_label: str | None = Field(default=None, min_length=1, max_length=100)
    destinations: list[str] | None = None
    origins: list[str] | None = None
    nights: int | None = Field(default=None, ge=1, le=90)
    days_ahead: int | None = Field(default=None, ge=1, le=730)
    sheet_name_map: dict[str, str] | None = None
    special_sheets: list[SpecialSheetConfig] | None = None
    is_active: bool | None = None
    currency: str | None = Field(default=None, pattern=_CURRENCY_PATTERN)
    max_stops: int | None = Field(default=None, ge=0, le=3)
    start_date: date | None = None
    end_date: date | None = None
    trip_type: str | None = None

    @field_validator("trip_type", mode="before")
    @classmethod
    def validate_trip_type_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return _normalize_trip_type(value)

    @field_validator("name", "destination_label")
    @classmethod
    def normalize_optional_text_fields(cls, value: str | None) -> str | None:
        return _normalize_text(value) if value is not None else None

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str] | None:
        normalized = _normalize_iata_codes(v)
        if isinstance(normalized, list):
            return normalized
        return v  # type: ignore[return-value]

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_optional_currency(cls, value: object) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("sheet_name_map")
    @classmethod
    def validate_optional_sheet_name_map(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        return {str(key).strip().upper(): _normalize_text(str(sheet)) for key, sheet in value.items()}

    @model_validator(mode="after")
    def validate_dates(self) -> "RouteGroupUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.trip_type == "multi_city" and self.special_sheets is not None:
            if len(self.special_sheets) != 1:
                raise ValueError("multi_city supports exactly one return-leg configuration")
        return self


class RouteGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    destination_label: str
    destinations: list[str]
    origins: list[str]
    nights: int
    days_ahead: int
    sheet_name_map: dict[str, str]
    special_sheets: list[SpecialSheetConfig]
    is_active: bool
    currency: str
    max_stops: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime
    trip_type: str


class PerOriginProgress(BaseModel):
    total: int
    collected: int


class ScrapeHealth(BaseModel):
    """Summary of recent scrape activity for a route group.

    status values: "ok", "never_scraped", "rate_limited", "quota_exhausted",
                   "auth_error", "error"
    """

    status: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_message: str | None = None
    errors_last_hour: int = 0
    successes_last_hour: int = 0


class RouteGroupProgress(BaseModel):
    route_group_id: uuid.UUID
    name: str
    total_dates: int
    dates_with_data: int
    coverage_percent: float
    last_scraped_at: datetime | None
    per_origin: dict[str, PerOriginProgress]
    scraped_dates: list[str] = Field(default_factory=list)
    health: ScrapeHealth = Field(default_factory=lambda: ScrapeHealth(status="never_scraped"))
