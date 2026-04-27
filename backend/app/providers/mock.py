"""
Mock/demo flight provider — generates realistic deterministic fake prices.
No API key needed. Activated by setting DEMO_MODE=true in .env.

Prices are seeded from the route+date so the same search always returns the
same numbers (consistent across browser refreshes during a demo).
"""
from __future__ import annotations

import hashlib
from datetime import date

from app.providers.base import ProviderResult

_AIRLINES = ["AC", "CX", "NH", "JL", "KL", "QR", "EK", "CA", "CZ", "BR"]

_PRICE_RANGES: dict[str, tuple[int, int]] = {
    "DPS": (950, 2600),
    "TYO": (900, 2500),
    "NRT": (900, 2500),
    "SHA": (980, 2700),
    "PVG": (980, 2700),
    "HKG": (850, 2300),
    "BKK": (800, 2100),
    "LHR": (1100, 3400),
    "CDG": (1100, 3400),
    "BJS": (220, 620),
    "PEK": (220, 620),
}
_DEFAULT_RANGE = (700, 3000)


def _rng(origin: str, destination: str, d: date, slot: int) -> int:
    key = f"{origin}{destination}{d.isoformat()}{slot}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16)  # noqa: S324


class MockProvider:
    name = "demo"

    def is_configured(self) -> bool:
        return True

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        low, high = _PRICE_RANGES.get(destination, _DEFAULT_RANGE)
        results = []
        for i in range(4):
            r = _rng(origin, destination, depart_date, i)
            price = low + (r % (high - low))
            price = round(price / 10) * 10          # round to nearest $10
            airline = _AIRLINES[r % len(_AIRLINES)]
            stops = r % 3
            duration = 480 + (r % 480)              # 8–16 hours in minutes
            if max_stops is not None and stops > max_stops:
                continue
            results.append(
                ProviderResult(
                    price=float(price),
                    currency=currency,
                    airline=airline,
                    deep_link="",
                    provider=self.name,
                    stops=stops,
                    duration_minutes=duration,
                )
            )
        return sorted(results, key=lambda r: r.price)
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
    ) -> list[ProviderResult]:
        # Round-trip simulation: outbound + return as separate one-way searches,
        # combined cheapest pairing. Keeps demo mode self-consistent so a
        # round-trip route group doesn't crash the collector with AttributeError.
        outbound = await self.search_one_way(
            origin, destination, depart_date, adults, cabin, currency, max_stops
        )
        inbound = await self.search_one_way(
            destination, origin, return_date, adults, cabin, currency, max_stops
        )
        if not outbound or not inbound:
            return outbound or inbound

        cheapest_in = inbound[0]
        return [
            ProviderResult(
                price=o.price + cheapest_in.price,
                currency=o.currency,
                airline=o.airline,
                deep_link="",
                provider=self.name,
                stops=max(o.stops, cheapest_in.stops),
                duration_minutes=o.duration_minutes + cheapest_in.duration_minutes,
            )
            for o in outbound
        ]

    async def close(self) -> None:
        pass
