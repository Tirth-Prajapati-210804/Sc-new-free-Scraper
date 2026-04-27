"""
Seed the two client route groups.
Usage: cd backend && python -m app.scripts.seed_route_groups
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.route_group import RouteGroup

GROUP_1 = {
    "name": "CAD-Tokyo-Shanghai-CAD",
    "destination_label": "TYO/SHA",
    "destinations": ["TYO", "SHA"],
    "origins": ["YYZ", "YVR", "YEG", "YYC", "YHZ", "YUL", "YOW"],
    "nights": 12,
    "days_ahead": 365,
    "sheet_name_map": {
        "YYZ": "YYZ",
        "YVR": "YVR",
        "YEG": "YEG",
        "YYC": "YYC",
        "YHZ": "YHZ",
        "YUL": "YUL",
        "YOW": "YOW",
    },
    "special_sheets": [
        {
            "name": "Osaka to Beijing",
            "origin": "KIX",
            "destination_label": "Beijing (Any)",
            "destinations": ["BJS", "PEK"],
            "columns": 4,
        }
    ],
}

GROUP_2 = {
    "name": "CAN-DPS",
    "destination_label": "DPS",
    "destinations": ["DPS"],
    "origins": ["YYZ", "YVR", "YEG", "YUL", "YOW", "YYC", "YHZ"],
    "nights": 11,
    "days_ahead": 306,
    "sheet_name_map": {
        "YYZ": "YYZ-DPS",
        "YVR": "YVR-DPS",
        "YEG": "YEG-DPS",
        "YUL": "YUL-DPS",
        "YOW": "YOW-DPS",
        "YYC": "YYC-DPS",
        "YHZ": "YHZ-DPS",
    },
    "special_sheets": [],
}


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        created = 0
        skipped = 0

        for data in [GROUP_1, GROUP_2]:
            existing = await session.execute(
                select(RouteGroup).where(RouteGroup.name == data["name"])
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP  {data['name']} (already exists)")
                skipped += 1
                continue

            group = RouteGroup(**data)
            session.add(group)
            print(f"  CREATE {data['name']}")
            created += 1

        await session.commit()
        print(f"\nDone — {created} created, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
