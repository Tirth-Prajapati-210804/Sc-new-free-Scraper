from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class ProviderResult:
    """One flight offer from a provider, already normalized."""

    price: float
    currency: str
    airline: str
    deep_link: str
    provider: str = ""
    duration_minutes: int = 0
    stops: int = 0
    raw_data: dict = field(default_factory=dict)


class FlightProvider(Protocol):
    """Protocol that all providers must implement."""

    name: str

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]: ...

    async def search_round_trip(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]: ...

    def is_configured(self) -> bool: ...

    async def close(self) -> None: ...
