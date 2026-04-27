from __future__ import annotations

from app.utils.location_resolver import search_location_suggestions


def test_search_location_suggestions_matches_prefixes() -> None:
    results = search_location_suggestions("c", limit=25)
    labels = {item["label"] for item in results}
    location_labels = {item["label"] for item in results if item["kind"] == "location"}

    assert "Canada" in labels
    assert "Calgary" in location_labels


def test_search_location_suggestions_includes_airport_codes() -> None:
    results = search_location_suggestions("cu", limit=10)

    assert any(item["kind"] == "airport_code" and "CUN" in item["codes"] for item in results)
