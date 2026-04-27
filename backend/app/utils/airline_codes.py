from __future__ import annotations

AIRLINE_MAP: dict[str, str] = {
    # ── Full names → IATA codes ───────────────────────────────────────────────
    # Major international carriers
    "AIR INDIA": "AI",
    "AIR CANADA": "AC",
    "AIR FRANCE": "AF",
    "AIR ASIA": "AK",
    "AIRASIA": "AK",
    "AIR ARABIA": "G9",
    "AIR CHINA": "CA",
    "AIR NEW ZEALAND": "NZ",
    "AIR TRANSAT": "TS",
    "ALASKA AIRLINES": "AS",
    "AMERICAN AIRLINES": "AA",
    "ANA": "NH",
    "ALL NIPPON AIRWAYS": "NH",
    "AUSTRIAN": "OS",
    "AUSTRIAN AIRLINES": "OS",
    "BANGKOK AIRWAYS": "PG",
    "BRITISH AIRWAYS": "BA",
    "CATHAY PACIFIC": "CX",
    "CHINA EASTERN": "MU",
    "CHINA SOUTHERN": "CZ",
    "DELTA": "DL",
    "DELTA AIR LINES": "DL",
    "EMIRATES": "EK",
    "ETIHAD": "EY",
    "ETIHAD AIRWAYS": "EY",
    "EVA AIR": "BR",
    "FINNAIR": "AY",
    "FLYDUBAI": "FZ",
    "GARUDA INDONESIA": "GA",
    "GULF AIR": "GF",
    "HAINAN AIRLINES": "HU",
    "HIMALAYA AIRLINES": "H9",
    "ICELANDAIR": "FI",
    "INDIGO": "6E",
    "INDONESIA AIRASIA": "QZ",
    "JAPAN AIRLINES": "JL",
    "JAPAN": "JL",
    "JET AIRWAYS": "9W",
    "JETBLUE": "B6",
    "JETBLUE AIRWAYS": "B6",
    "KENYA AIRWAYS": "KQ",
    "KLM": "KL",
    "KLM ROYAL DUTCH AIRLINES": "KL",
    "KOREAN AIR": "KE",
    "LUFTHANSA": "LH",
    "LUFTHANSANA": "LH",
    "LUTHANSA": "LH",
    "MALAYSIA AIRLINES": "MH",
    "MALAYSIA": "MH",
    "MALINDO AIR": "OD",
    "OMAN AIR": "WY",
    "PHILIPPINES AIRLINES": "PR",
    "PHILIPPINE AIRLINES": "PR",
    "QATAR AIRWAYS": "QR",
    "ROYAL JORDANIAN": "RJ",
    "SCOOT": "TR",
    "SINGAPORE AIRLINES": "SQ",
    "SRILANKAN AIRLINES": "UL",
    "SWISS": "LX",
    "SWISS INTERNATIONAL AIR LINES": "LX",
    "THAI AIRWAYS": "TG",
    "THAI AIRWAYS INTERNATIONAL": "TG",
    "THAI AIRASIA": "FD",
    "THAI LION AIR": "SL",
    "THAI SMILE": "WE",
    "TIGERAIR": "TR",
    "TURKISH AIRLINES": "TK",
    "UNITED": "UA",
    "UNITED AIRLINES": "UA",
    "VIETNAM AIRLINES": "VN",
    "VIETJET": "VJ",
    "VIETJET AIR": "VJ",
    "VIETJET AVIATION": "VJ",
    "XIAMEN AIRLINES": "MF",

    # ── IATA codes → pass through ─────────────────────────────────────────────
    "6E": "6E",   # IndiGo
    "9W": "9W",   # Jet Airways
    "AA": "AA",
    "AC": "AC",
    "AF": "AF",
    "AI": "AI",
    "AK": "AK",
    "AS": "AS",
    "AY": "AY",
    "B6": "B6",
    "BA": "BA",
    "BR": "BR",
    "CA": "CA",
    "CE": "CE",
    "CP": "CP",
    "CS": "CS",
    "CX": "CX",
    "CZ": "CZ",
    "DL": "DL",
    "EA": "EA",
    "EK": "EK",
    "EY": "EY",
    "FD": "FD",
    "FI": "FI",
    "FZ": "FZ",
    "G9": "G9",
    "GA": "GA",
    "GF": "GF",
    "H9": "H9",
    "HKA": "HKA",
    "HU": "HU",
    "JL": "JL",
    "KA": "KA",
    "KE": "KE",
    "KL": "KL",
    "KQ": "KQ",
    "LH": "LH",
    "LX": "LX",
    "MF": "MF",
    "MH": "MH",
    "MU": "MU",
    "NH": "NH",
    "NZ": "NZ",
    "OD": "OD",
    "OS": "OS",
    "PA": "PA",
    "PG": "PG",
    "PR": "PR",
    "QA": "QA",
    "QR": "QR",
    "QZ": "QZ",
    "RJ": "RJ",
    "SL": "SL",
    "SQ": "SQ",
    "TA": "TA",
    "TG": "TG",
    "TK": "TK",
    "TR": "TR",
    "TS": "TS",
    "UA": "UA",
    "UL": "UL",
    "VJ": "VJ",
    "VN": "VN",
    "WE": "WE",
    "WY": "WY",

    # ── Partial / garbled forms seen in provider responses ────────────────────
    "J A": "JL",
    "EVA A": "BR",
    "K A": "KA",
    "A F": "AF",
    "A I": "AI",
    "C A": "CA",
    "C P": "CP",
}


# Reverse lookup: IATA code → human-readable airline name. Built from
# AIRLINE_MAP so the two stay in sync. When several aliases map to the same
# IATA, we keep the first canonical full name encountered.
_IATA_TO_NAME: dict[str, str] = {}
for _name, _code in AIRLINE_MAP.items():
    if _name == _code:
        continue  # skip pass-through "AC" → "AC" entries
    if _code not in _IATA_TO_NAME:
        _IATA_TO_NAME[_code] = _name.title()


def normalize_airline(raw: str) -> str:
    """Return a human-readable airline name for display in exports / UI.

    The collector previously compressed every airline name down to a 2-letter
    IATA code ("Icelandair" → "FI"), which made the Excel export unreadable
    for clients. We now keep whatever full name the provider returned and only
    expand bare IATA codes back into readable names.
    """
    if not raw or not raw.strip():
        return "-"
    cleaned = raw.strip()
    upper = cleaned.upper()

    # Bare IATA code from the provider (e.g. "FI") — expand to full name.
    if len(cleaned) <= 3 and upper in _IATA_TO_NAME:
        return _IATA_TO_NAME[upper]

    # Otherwise the provider already gave us a full name; preserve it as-is.
    return cleaned[:64]
