from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSegment:
    origin: str
    destinations: list[str]
    trip_type: str
    nights: int | None


def iter_group_segments(group) -> list[RouteSegment]:
    segments: list[RouteSegment] = []

    for origin in group.origins or []:
        segments.append(
            RouteSegment(
                origin=str(origin).strip().upper(),
                destinations=[str(destination).strip().upper() for destination in (group.destinations or [])],
                trip_type=group.trip_type or "one_way",
                nights=group.nights,
            )
        )

    for sheet in group.special_sheets or []:
        origin = str(sheet.get("origin") or "").strip().upper()
        destinations = [
            str(destination).strip().upper()
            for destination in (sheet.get("destinations") or [])
            if str(destination).strip()
        ]

        if not origin or not destinations:
            continue

        segments.append(
            RouteSegment(
                origin=origin,
                destinations=destinations,
                trip_type="one_way",
                nights=None,
            )
        )

    return segments
