"""
Live verification for the ScrapingBee provider.

Run this after creating a ScrapingBee account and copying your API key.
It exercises one-way, round-trip, and open-jaw (multi-city) searches through
the app's real ScrapingBee provider implementation and prints the parsed
results.

Usage (from the backend/ directory):

    # PowerShell
    $env:SCRAPINGBEE_API_KEY = "your-key-here"
    python -m scripts.verify_scrapingbee

    # bash
    SCRAPINGBEE_API_KEY=your-key-here python -m scripts.verify_scrapingbee

Optional overrides:

    VERIFY_ORIGIN=YYZ VERIFY_DESTINATION=NRT VERIFY_NIGHTS=12 \
    VERIFY_OPEN_JAW_RETURN_ORIGIN=BUD VERIFY_CURRENCY=USD \
    python -m scripts.verify_scrapingbee

Exit codes:
    0  - everything worked and parsed results returned
    1  - missing key or unrecoverable error
    2  - request succeeded but no results were returned for any scenario
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta

from app.providers.scrapingbee import ScrapingBeeProvider


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


async def main() -> int:
    api_key = os.environ.get("SCRAPINGBEE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: SCRAPINGBEE_API_KEY env var is not set.", file=sys.stderr)
        print("Get your key from https://www.scrapingbee.com/dashboard/.", file=sys.stderr)
        return 1

    origin = _env("VERIFY_ORIGIN", "YYZ")
    destination = _env("VERIFY_DESTINATION", "NRT")
    nights = int(_env("VERIFY_NIGHTS", "12"))
    days_out = int(_env("VERIFY_DAYS_OUT", "45"))
    open_jaw_return_origin = _env("VERIFY_OPEN_JAW_RETURN_ORIGIN", "BUD")
    currency = _env("VERIFY_CURRENCY", "USD")

    depart = date.today() + timedelta(days=days_out)
    return_date = depart + timedelta(days=nights)

    provider = ScrapingBeeProvider(
        api_key=api_key,
        country_code=_env("SCRAPINGBEE_COUNTRY_CODE", "us"),
        premium_proxy=_env("SCRAPINGBEE_PREMIUM_PROXY", "false").lower() in {"1", "true", "yes"},
        stealth_proxy=_env("SCRAPINGBEE_STEALTH_PROXY", "false").lower() in {"1", "true", "yes"},
    )

    print("=" * 64)
    print("ScrapingBee live verification")
    print(f"  Key:          {'*' * 4}{api_key[-4:]} (length {len(api_key)})")
    print(f"  Currency:     {currency}")
    print(f"  Depart date:  {depart.isoformat()}  (today + {days_out} days)")
    print(f"  Return date:  {return_date.isoformat()}  ({nights} nights)")
    print("=" * 64)

    try:
        print(f"\n[1/3] ONE WAY  {origin} -> {destination}  on {depart.isoformat()}")
        one_way = await provider.search_one_way(
            origin=origin,
            destination=destination,
            depart_date=depart,
            currency=currency,
        )
        _print_results(one_way)

        print(f"\n[2/3] ROUND TRIP  {origin} -> {destination} -> {origin}")
        print(f"      depart {depart.isoformat()} / return {return_date.isoformat()}")
        round_trip = await provider.search_round_trip(
            origin=origin,
            destination=destination,
            depart_date=depart,
            return_date=return_date,
            currency=currency,
        )
        _print_results(round_trip)

        print(f"\n[3/3] OPEN JAW  {origin} -> {destination}  /  {open_jaw_return_origin} -> {origin}")
        print(f"      outbound {depart.isoformat()} / return {return_date.isoformat()}")
        open_jaw = await provider.search_multi_city(
            legs=[
                {
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": depart,
                },
                {
                    "departure_id": open_jaw_return_origin,
                    "arrival_id": origin,
                    "outbound_date": return_date,
                },
            ],
            currency=currency,
        )
        _print_results(open_jaw)

        empty_count = sum(1 for r in (one_way, round_trip, open_jaw) if not r)
        if empty_count == 3:
            print("\nAll three searches returned no data.")
            print("Try a busier route, a closer departure date, or premium proxy mode.")
            return 2

        print("\nVerification complete. ScrapingBee returned live data.")
        return 0

    except Exception as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await provider.close()


def _print_results(results) -> None:
    if not results:
        print("  (no data returned)")
        return

    print(f"  {len(results)} offer(s):")
    for result in results[:5]:
        print(
            f"    {result.airline:<20} {result.currency} {result.price:>9,.2f}"
            f"  stops={result.stops}  duration={result.duration_minutes}m"
        )
        if result.deep_link:
            print(f"      link: {result.deep_link[:120]}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
