from __future__ import annotations

from app.utils.airline_codes import normalize_airline


def test_iata_code_expands_to_full_name() -> None:
    assert normalize_airline("EK") == "Emirates"
    assert normalize_airline("LH") == "Lufthansa"
    assert normalize_airline("FI") == "Icelandair"


def test_iata_code_case_insensitive() -> None:
    assert normalize_airline("ek") == "Emirates"
    assert normalize_airline("Ac") == "Air Canada"


def test_full_name_passes_through_unchanged() -> None:
    assert normalize_airline("Air Canada") == "Air Canada"
    assert normalize_airline("Emirates") == "Emirates"
    assert normalize_airline("LUFTHANSA CARGO") == "LUFTHANSA CARGO"


def test_unknown_short_code_passes_through() -> None:
    assert normalize_airline("XX") == "XX"


def test_empty_returns_dash() -> None:
    assert normalize_airline("") == "-"
    assert normalize_airline("  ") == "-"


def test_long_name_truncated_to_64() -> None:
    long = "Some Very Long Airline Name " * 5
    result = normalize_airline(long)
    assert len(result) <= 64
    assert result == long.strip()[:64]
