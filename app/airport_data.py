"""Server-side airport lookup and autocomplete.

Pre-loads a trimmed airport dataset (~158KB) and provides instant
search by IATA code, city, state, or airport name.
"""

import json
import os
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_airports: list[dict] = []
_iata_to_city: dict[str, str] = {}


def _load():
    """Load trimmed airport dataset once."""
    global _airports, _iata_to_city
    if _airports:
        return
    path = _DATA_DIR / "airports_lite.json"
    if not path.exists():
        return
    with open(path, "r") as f:
        _airports = json.load(f)
    for a in _airports:
        city = a.get("city", "")
        state = a.get("state", "")
        if city:
            _iata_to_city[a["iata"]] = f"{city}, {state}" if state else city


def search_airports(query: str, limit: int = 15) -> list[dict]:
    """Search airports by IATA code, city, state, or name.

    Returns list of matching airport dicts with iata, name, city, state.
    Special: if query matches a state abbreviation exactly, prepends a
    'bulk' entry with all airports in that state.
    """
    _load()
    if not query or len(query) < 2:
        return []

    q = query.lower().strip()
    results = []

    # Check for exact state match → offer bulk selection
    state_matches = [a for a in _airports if a.get("state", "").lower() == q]
    if state_matches:
        results.append({
            "type": "STATE_BULK",
            "title": f"All {len(state_matches)} airports in {state_matches[0]['state']}",
            "subtitle": ", ".join(a["iata"] for a in state_matches[:20]),
            "code": ", ".join(a["iata"] for a in state_matches),
        })

    # Individual airport matches
    count = 0
    for a in _airports:
        if count >= limit:
            break
        if (
            q in a["iata"].lower()
            or q in a.get("city", "").lower()
            or q in a.get("state", "").lower()
            or q in a.get("name", "").lower()
        ):
            results.append({
                "type": "SINGLE",
                "title": f"{a['name']} ({a['iata']})",
                "subtitle": f"{a.get('city', '')}, {a.get('state', '')}",
                "code": a["iata"],
            })
            count += 1

    return results


def iata_to_city(code: str) -> str:
    """Resolve IATA code to 'City, State' for hotel searches."""
    _load()
    return _iata_to_city.get(code.upper(), code)


def get_all_airports() -> list[dict]:
    """Return the full trimmed airport list."""
    _load()
    return _airports
