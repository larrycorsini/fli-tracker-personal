"""Pinned featured-trip searches for morning digest + site spotlight."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from fli.cli.utils import serialize_flight_result
from fli.core import (
    build_flight_segments,
    parse_airlines,
    parse_cabin_class,
    parse_max_stops,
    resolve_airport,
)
from fli.models import FlightSearchFilters, PassengerInfo
from fli.search import SearchFlights
from tracker_config import (
    EXCLUDED_AIRLINES,
    FEATURED_SEARCHES,
    FEATURED_SEARCHES_JSON,
    FEATURED_SEARCHES_PUBLIC_JSON,
    SITE_URL,
)
from tracker_io import atomic_write_json

log = logging.getLogger("featured_searches")

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


def _parse_iso(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str)
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def active_featured_searches(when: datetime | None = None) -> list[dict]:
    """Return featured specs whose return date is still today or later."""
    when = when or datetime.now()
    today = when.date()
    active: list[dict] = []
    for spec in FEATURED_SEARCHES:
        ret = _parse_iso(str(spec.get("ret_date", "")))
        if ret is None:
            continue
        if ret.date() < today:
            continue
        active.append(spec)
    return active


def _window_matches(out_dep: datetime, out_date: str, windows: list[dict]) -> bool:
    for window in windows:
        if window.get("date") != out_date:
            continue
        if "after_hour" in window and out_dep.hour >= int(window["after_hour"]):
            return True
        if "before_hour" in window and out_dep.hour < int(window["before_hour"]):
            return True
    return False


def flight_matches_featured(flight: dict, spec: dict) -> bool:
    """Return whether a find_direct-style flight row matches featured windows."""
    if flight.get("price") is None:
        return False
    origins = set(spec.get("origins") or [])
    if origins and flight.get("origin") not in origins:
        return False
    if flight.get("destination") != spec.get("destination"):
        return False
    if flight.get("ret_date") != spec.get("ret_date"):
        return False
    out_date = flight.get("out_date") or ""
    windows = spec.get("out_windows") or []
    allowed_dates = {w.get("date") for w in windows}
    if out_date not in allowed_dates:
        return False
    out_dep = _parse_iso(str(flight.get("out_dep") or ""))
    if out_dep is None:
        return False
    return _window_matches(out_dep, out_date, windows)


def match_featured_from_results(all_results: dict[str, list[dict]], spec: dict) -> list[dict]:
    """Pull matching priced rows from regional search results."""
    region = spec.get("region") or ""
    pool: list[dict] = []
    if region and isinstance(all_results.get(region), list):
        pool.extend(all_results[region])
    for flights in all_results.values():
        if not isinstance(flights, list):
            continue
        pool.extend(flights)

    matched = [row for row in pool if isinstance(row, dict) and flight_matches_featured(row, spec)]
    # Dedupe by origin/out_dep/ret_arr/price/url
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in matched:
        key = (
            row.get("origin"),
            row.get("out_dep"),
            row.get("ret_arr"),
            row.get("price"),
            row.get("url"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    limit = int(spec.get("max_options") or 6)
    return _diversify_featured_rows(unique, limit)


def _search_pair(
    searcher: SearchFlights,
    origin: str,
    dest: str,
    out_date: str,
    ret_date: str,
    max_stops: str,
) -> list[dict]:
    origin_airport = resolve_airport(origin)
    dest_airport = resolve_airport(dest)
    stops = parse_max_stops(max_stops)
    seat = parse_cabin_class("ECONOMY")
    exclude_airlines = parse_airlines(EXCLUDED_AIRLINES)
    segments, trip_type = build_flight_segments(
        origin=origin_airport,
        destination=dest_airport,
        departure_date=out_date,
        return_date=ret_date,
    )
    filters = FlightSearchFilters(
        trip_type=trip_type,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=segments,
        stops=stops,
        seat_type=seat,
        airlines_exclude=exclude_airlines,
        show_all_results=True,
    )

    results = None
    for attempt in range(MAX_RETRIES):
        try:
            results = searcher.search(filters)
            break
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
            else:
                raise exc

    if not results:
        return []

    rows: list[dict] = []
    for result in results:
        # Round-trip search returns tuples of FlightResult; serialize handles both.
        try:
            booking_url = searcher.build_flight_booking_url(result)
            flight = serialize_flight_result(result, booking_url=booking_url)
        except Exception:
            continue
        if flight.get("price") is None:
            continue
        try:
            out_dep = flight["outbound"]["legs"][0]["departure_time"]
            ret_arr = flight["return"]["legs"][-1]["arrival_time"]
            airline_name = flight["outbound"]["legs"][0]["airline"]["name"]
        except (KeyError, TypeError, IndexError):
            continue
        rows.append(
            {
                "origin": origin,
                "destination": dest,
                "out_date": out_date,
                "ret_date": ret_date,
                "price": flight["price"],
                "airline": airline_name,
                "out_dep": out_dep,
                "ret_arr": ret_arr,
                "url": flight.get("booking_url") or "",
            }
        )
    return rows


def _diversify_featured_rows(rows: list[dict], limit: int) -> list[dict]:
    """Prefer variety across origin + departure window, then cheapest returns."""
    rows = sorted(
        rows,
        key=lambda r: (float(r["price"]), r.get("out_dep") or "", r.get("origin") or ""),
    )
    picked: list[dict] = []
    seen_window: set[tuple] = set()
    # Pass 1: one cheapest option per origin + outbound departure
    for row in rows:
        key = (row.get("origin"), row.get("out_dep"))
        if key in seen_window:
            continue
        seen_window.add(key)
        picked.append(row)
        if len(picked) >= limit:
            return picked
    # Pass 2: fill remaining slots with next-cheapest alternate returns
    for row in rows:
        if row in picked:
            continue
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def search_featured_spec(spec: dict, *, searcher: SearchFlights | None = None) -> list[dict]:
    """Live-search one featured trip (nonstop, excluded ULCC) and apply time windows."""
    searcher = searcher or SearchFlights()
    dest = spec["destination"]
    ret_date = spec["ret_date"]
    max_stops = str(spec.get("max_stops") or "0")
    windows = spec.get("out_windows") or []
    out_dates = sorted({w["date"] for w in windows if w.get("date")})
    collected: list[dict] = []

    for origin in spec.get("origins") or []:
        for out_date in out_dates:
            try:
                rows = _search_pair(searcher, origin, dest, out_date, ret_date, max_stops)
            except Exception as exc:
                log.warning(
                    "Featured search failed %s→%s %s/%s: %s",
                    origin,
                    dest,
                    out_date,
                    ret_date,
                    exc,
                )
                continue
            for row in rows:
                if flight_matches_featured(row, spec):
                    collected.append(row)
            time.sleep(0.5)

    limit = int(spec.get("max_options") or 6)
    return _diversify_featured_rows(collected, limit)


def _option_label(out_dep: str) -> str:
    dt = _parse_iso(out_dep)
    if dt is None:
        return ""
    # Wed afternoon / Thu morning style cues
    if dt.weekday() == 2 and dt.hour >= 12:
        return "Wed afternoon"
    if dt.weekday() == 3 and dt.hour < 12:
        return "Thu morning"
    return dt.strftime("%a")


def format_featured_option(row: dict, spec: dict) -> dict:
    """Serialize one option for public JSON / alerts."""
    out_dep = str(row.get("out_dep") or "")
    ret_arr = str(row.get("ret_arr") or "")
    out_dt = _parse_iso(out_dep)
    ret_dt = _parse_iso(ret_arr)
    return {
        "origin": row.get("origin"),
        "destination": row.get("destination") or spec.get("destination"),
        "airline": row.get("airline") or "",
        "price": int(row["price"]) if row.get("price") is not None else None,
        "outDate": row.get("out_date"),
        "retDate": row.get("ret_date"),
        "outDep": out_dep,
        "retArr": ret_arr,
        "outDepFmt": out_dt.strftime("%a, %b %d, %I:%M %p") if out_dt else out_dep,
        "retArrFmt": ret_dt.strftime("%a, %b %d, %I:%M %p") if ret_dt else ret_arr,
        "windowLabel": _option_label(out_dep),
        "url": row.get("url") or "",
    }


def build_featured_payload(
    specs_with_options: list[tuple[dict, list[dict]]],
    *,
    last_updated: str | None = None,
    last_updated_at: str | None = None,
) -> dict:
    """Build featured_searches.json / public payload."""
    searches = []
    for spec, rows in specs_with_options:
        options = [format_featured_option(row, spec) for row in rows]
        options = [opt for opt in options if opt.get("price") is not None]
        best = min((opt["price"] for opt in options), default=None)
        searches.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "blurb": spec.get("blurb") or "",
                "region": spec.get("region") or "",
                "destination": spec.get("destination"),
                "retDate": spec.get("ret_date"),
                "bestPrice": best,
                "siteUrl": f"{SITE_URL.rstrip('/')}/#featured-{spec['id']}",
                "regionUrl": f"{SITE_URL.rstrip('/')}/?tab={spec.get('region') or 'DFW'}",
                "options": options,
            }
        )
    return {
        "lastUpdated": last_updated,
        "lastUpdatedAt": last_updated_at,
        "searches": searches,
    }


def collect_featured_options(
    all_results: dict[str, list[dict]] | None = None,
    *,
    live_search: bool = False,
) -> list[tuple[dict, list[dict]]]:
    """Resolve options for each active featured spec."""
    results = all_results or {}
    searcher = SearchFlights() if live_search else None
    out: list[tuple[dict, list[dict]]] = []
    for spec in active_featured_searches():
        rows = match_featured_from_results(results, spec)
        if live_search and (not rows or len(rows) < 2):
            live_rows = search_featured_spec(spec, searcher=searcher)
            # Prefer live when it found anything; keep cheapest unique mix
            by_key: dict[tuple, dict] = {}
            for row in rows + live_rows:
                key = (row.get("origin"), row.get("out_dep"), row.get("ret_arr"), row.get("price"))
                by_key[key] = row
            limit = int(spec.get("max_options") or 6)
            rows = _diversify_featured_rows(list(by_key.values()), limit)
        out.append((spec, rows))
    return out


def write_featured_searches(
    all_results: dict[str, list[dict]] | None = None,
    *,
    live_search: bool = False,
    last_updated: str | None = None,
    last_updated_at: str | None = None,
) -> dict:
    """Search/match featured trips and write featured_searches.json."""
    pairs = collect_featured_options(all_results, live_search=live_search)
    payload = build_featured_payload(
        pairs, last_updated=last_updated, last_updated_at=last_updated_at
    )
    atomic_write_json(FEATURED_SEARCHES_JSON, payload)
    log.info(
        "Wrote %s (%d search(es), %d option(s))",
        FEATURED_SEARCHES_JSON,
        len(payload.get("searches") or []),
        sum(len(s.get("options") or []) for s in payload.get("searches") or []),
    )
    return payload


def load_featured_searches() -> dict:
    """Load featured search payload from root or public JSON."""
    for path in (FEATURED_SEARCHES_JSON, FEATURED_SEARCHES_PUBLIC_JSON):
        if not os.path.exists(path):
            continue
        try:
            import json

            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        searches = data.get("searches", [])
        if not isinstance(searches, list):
            searches = []
        return {**data, "searches": [s for s in searches if isinstance(s, dict)]}
    return {"searches": []}


def flatten_featured_for_alert(payload: dict | None = None) -> list[dict]:
    """Flatten featured options into alert-friendly deal rows (best per search)."""
    payload = payload if payload is not None else load_featured_searches()
    deals: list[dict] = []
    for search in payload.get("searches") or []:
        options = [o for o in (search.get("options") or []) if o.get("price") is not None]
        if not options:
            continue
        best = min(options, key=lambda o: o["price"])
        deals.append(
            {
                "id": search.get("id"),
                "title": search.get("title") or "Featured trip",
                "blurb": search.get("blurb") or "",
                "region": search.get("region") or "",
                "price": int(best["price"]),
                "origin": best.get("origin"),
                "destination": best.get("destination"),
                "out_date": best.get("outDate"),
                "ret_date": best.get("retDate"),
                "airline": best.get("airline") or "",
                "window_label": best.get("windowLabel") or "",
                "url": best.get("url") or "",
                "site_url": search.get("siteUrl") or f"{SITE_URL}/#featured",
                "options": options[:3],
            }
        )
    return deals


def main() -> int:
    """CLI: refresh featured_searches.json via live Google Flights search."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from datetime import timezone
    from zoneinfo import ZoneInfo

    from tracker_config import DISPLAY_TIMEZONE

    instant = datetime.now(timezone.utc)
    local = instant.astimezone(ZoneInfo(DISPLAY_TIMEZONE))
    label = local.strftime("%a, %b %d, %Y at %I:%M %p %Z")
    write_featured_searches(
        live_search=True, last_updated=label, last_updated_at=instant.isoformat()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
