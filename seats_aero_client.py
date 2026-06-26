"""Seats.aero Partner API client — cached award search with daily quota tracking.

Cached Search returns one-way segment mileage per departure date. Round-trip
estimates use ``lowest_one_way * 2`` (documented limitation; return leg may differ).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from tracker_config import (
    SEATS_AERO_DAILY_LIMIT,
    SEATS_AERO_DAILY_RESERVE,
    SEATS_AERO_MAX_CALLS_PER_RUN,
)
from tracker_io import atomic_write_json

log = logging.getLogger("seats_aero")

BASE_URL = "https://seats.aero/partnerapi/search"
USAGE_PATH = Path(__file__).resolve().parent / "app" / "data" / "seats_aero_usage.json"

# Fli cabin enum → seats.aero ``cabins`` query value (economy|premium|business|first).
CABIN_TO_API: dict[str, str] = {
    "BUSINESS": "business",
    "PREMIUM_ECONOMY": "premium",
}

# seats.aero availability fields per cabin letter.
_CABIN_FIELDS: dict[str, tuple[str, str, str]] = {
    "BUSINESS": ("JAvailable", "JMileageCost", "JAirlines"),
    "PREMIUM_ECONOMY": ("WAvailable", "WMileageCost", "WAirlines"),
}


@dataclass(frozen=True)
class AwardAvailability:
    """One-way award segment from cached search."""

    origin: str
    destination: str
    out_date: str
    cabin: str
    points_one_way: int
    mileage_program: str
    airlines: str

    @property
    def points_round_trip_estimate(self) -> int:
        """Heuristic round-trip points (outbound lowest × 2)."""
        return self.points_one_way * 2


def is_enabled() -> bool:
    """Return whether seats.aero integration is active (API key set, not disabled)."""
    if os.environ.get("SEATS_AERO_DISABLED", "").lower() in ("1", "true", "yes"):
        return False
    return bool(os.environ.get("SEATS_AERO_API_KEY", "").strip())


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _daily_budget() -> int:
    return SEATS_AERO_DAILY_LIMIT - SEATS_AERO_DAILY_RESERVE


def _load_usage() -> dict[str, Any]:
    if not USAGE_PATH.exists():
        return {"utc_date": _utc_today(), "daily_count": 0, "run_count": 0}
    try:
        with USAGE_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read seats.aero usage file: %s", exc)
        return {"utc_date": _utc_today(), "daily_count": 0, "run_count": 0}
    if not isinstance(data, dict):
        return {"utc_date": _utc_today(), "daily_count": 0, "run_count": 0}
    if data.get("utc_date") != _utc_today():
        return {"utc_date": _utc_today(), "daily_count": 0, "run_count": 0}
    return {
        "utc_date": _utc_today(),
        "daily_count": int(data.get("daily_count", 0)),
        "run_count": int(data.get("run_count", 0)),
    }


def _save_usage(data: dict[str, Any]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(str(USAGE_PATH), data)


def begin_run() -> None:
    """Reset per-run call counter (daily counter persists until UTC midnight)."""
    usage = _load_usage()
    usage["run_count"] = 0
    _save_usage(usage)


def get_usage_summary() -> dict[str, int]:
    """Return current daily and per-run API call counts."""
    usage = _load_usage()
    return {
        "daily_count": usage["daily_count"],
        "daily_budget": _daily_budget(),
        "run_count": usage["run_count"],
        "run_budget": SEATS_AERO_MAX_CALLS_PER_RUN,
    }


def _can_make_call() -> bool:
    usage = _load_usage()
    if usage["daily_count"] >= _daily_budget():
        log.warning(
            "seats.aero daily budget exhausted (%d/%d, %d reserved for manual use)",
            usage["daily_count"],
            _daily_budget(),
            SEATS_AERO_DAILY_RESERVE,
        )
        return False
    if usage["run_count"] >= SEATS_AERO_MAX_CALLS_PER_RUN:
        log.warning(
            "seats.aero per-run limit reached (%d/%d)",
            usage["run_count"],
            SEATS_AERO_MAX_CALLS_PER_RUN,
        )
        return False
    return True


def _record_call() -> None:
    usage = _load_usage()
    usage["daily_count"] = int(usage.get("daily_count", 0)) + 1
    usage["run_count"] = int(usage.get("run_count", 0)) + 1
    _save_usage(usage)


def _parse_mileage_cost(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "0":
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_availability_rows(
    rows: list[Any],
    *,
    fli_cabins: tuple[str, ...],
) -> list[AwardAvailability]:
    results: list[AwardAvailability] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out_date = str(row.get("Date", ""))[:10]
        if not out_date:
            continue
        route = row.get("Route") if isinstance(row.get("Route"), dict) else {}
        origin = str(route.get("OriginAirport") or row.get("OriginAirport") or "").upper()
        dest_raw = route.get("DestinationAirport") or row.get("DestinationAirport") or ""
        destination = str(dest_raw).upper()
        program = str(row.get("Source") or route.get("Source") or "")

        for cabin in fli_cabins:
            avail_key, cost_key, airlines_key = _CABIN_FIELDS[cabin]
            if not row.get(avail_key):
                continue
            one_way = _parse_mileage_cost(row.get(cost_key))
            if one_way is None:
                continue
            airlines = str(row.get(airlines_key) or "").strip()
            results.append(
                AwardAvailability(
                    origin=origin,
                    destination=destination,
                    out_date=out_date,
                    cabin=cabin,
                    points_one_way=one_way,
                    mileage_program=program,
                    airlines=airlines,
                )
            )
    return results


def cached_search(
    origin: str,
    dest: str,
    start_date: str,
    end_date: str,
    cabin: str,
    *,
    take: int = 50,
) -> list[AwardAvailability]:
    """Query cached award availability for one origin, destination, and cabin.

    Makes at most one API call; returns parsed one-way award rows. Skips the
    HTTP request when disabled or quota is exhausted.
    """
    if not is_enabled():
        return []
    if cabin not in CABIN_TO_API:
        log.warning("Unsupported cabin for seats.aero: %s", cabin)
        return []
    if not _can_make_call():
        return []

    api_key = os.environ["SEATS_AERO_API_KEY"].strip()
    params = {
        "origin_airport": origin.upper(),
        "destination_airport": dest.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "cabins": CABIN_TO_API[cabin],
        "order_by": "lowest_mileage",
        "take": max(10, min(50, take)),
    }
    headers = {"Partner-Authorization": api_key}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        log.warning("seats.aero cached search failed %s→%s: %s", origin, dest, exc)
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("seats.aero invalid JSON %s→%s: %s", origin, dest, exc)
        return []

    _record_call()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    return _parse_availability_rows(rows, fli_cabins=(cabin,))


def cached_search_destination(
    origins: list[str],
    dest: str,
    start_date: str,
    end_date: str,
    *,
    cabins: tuple[str, ...] = ("BUSINESS", "PREMIUM_ECONOMY"),
    take: int = 50,
) -> list[AwardAvailability]:
    """One cached search per destination — all origins and cabins in a single call."""
    if not is_enabled():
        return []
    if not origins:
        return []
    api_cabins = [CABIN_TO_API[c] for c in cabins if c in CABIN_TO_API]
    if not api_cabins:
        return []
    if not _can_make_call():
        return []

    api_key = os.environ["SEATS_AERO_API_KEY"].strip()
    params = {
        "origin_airport": ",".join(o.upper() for o in origins),
        "destination_airport": dest.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "cabins": ",".join(api_cabins),
        "order_by": "lowest_mileage",
        "take": max(10, min(50, take)),
    }
    headers = {"Partner-Authorization": api_key}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        log.warning("seats.aero cached search failed →%s: %s", dest, exc)
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("seats.aero invalid JSON →%s: %s", dest, exc)
        return []

    _record_call()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    return _parse_availability_rows(rows, fli_cabins=cabins)


def lookup_award(
    availabilities: list[AwardAvailability],
    *,
    origin: str,
    dest: str,
    out_date: str,
    cabin: str,
) -> AwardAvailability | None:
    """Best matching one-way award for a specific origin, date, and cabin."""
    origin_u = origin.upper()
    dest_u = dest.upper()
    matches = [
        row
        for row in availabilities
        if row.origin == origin_u
        and row.destination == dest_u
        and row.out_date == out_date
        and row.cabin == cabin
    ]
    if not matches:
        return None
    return min(matches, key=lambda row: row.points_one_way)
