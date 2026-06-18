"""Multi-region flight search for Fli-Tracker.

Two-phase pipeline:
  Phase 1 — SearchDates (price-graph equivalent) to shortlist cheap date pairs.
  Phase 2 — SearchFlights on the shortlist for times, airlines, and booking URLs.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from threading import Lock

from fli.cli.utils import serialize_flight_result
from fli.core import (
    build_date_search_segments,
    build_flight_segments,
    parse_airlines,
    parse_cabin_class,
    parse_max_stops,
    resolve_airport,
)
from fli.models import DateSearchFilters, FlightSearchFilters, PassengerInfo
from fli.search import SearchDates, SearchFlights
from fli.search.dates import DatePrice

from tracker_config import (
    DOMESTIC_TRIP_DURATIONS,
    EXCLUDED_AIRLINES,
    INTERNATIONAL_TRIP_DURATIONS,
    ORIGINS,
    OUTPUT_JSON,
    REGIONS,
    SHORTLIST_SIZE,
    SHORTLIST_SIZE_TEST,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("find_direct")

_flight_searcher: SearchFlights | None = None
_dates_searcher: SearchDates | None = None
_searcher_lock = Lock()
_stats = {"dates_ok": 0, "dates_empty": 0, "flights_ok": 0, "flights_empty": 0, "errors": 0}
_stats_lock = Lock()
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


def _get_flight_searcher() -> SearchFlights:
    global _flight_searcher
    with _searcher_lock:
        if _flight_searcher is None:
            _flight_searcher = SearchFlights()
        return _flight_searcher


def _get_dates_searcher() -> SearchDates:
    global _dates_searcher
    with _searcher_lock:
        if _dates_searcher is None:
            _dates_searcher = SearchDates()
        return _dates_searcher


def atomic_write_json(path: str, data: object) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp_path, path)


def _domestic_time_valid(out_dep: datetime, ret_arr: datetime) -> bool:
    out_valid = False
    if out_dep.weekday() == 2 and out_dep.hour >= 12:
        out_valid = True
    elif out_dep.weekday() == 3 and out_dep.hour < 12:
        out_valid = True
    elif out_dep.weekday() == 4:
        out_valid = True
    return out_valid and ret_arr.hour < 16


def _domestic_date_pair_valid(out_date: datetime, ret_date: datetime) -> bool:
    if out_date.weekday() not in (2, 3, 4):
        return False
    return ret_date.weekday() in (5, 6)


def _flight_matches(flight: dict, r_type: str) -> bool:
    if flight.get("price") is None:
        return False
    try:
        out_dep = datetime.fromisoformat(flight["outbound"]["legs"][0]["departure_time"])
        ret_arr = datetime.fromisoformat(flight["return"]["legs"][-1]["arrival_time"])
    except (KeyError, TypeError, ValueError):
        return False
    if r_type == "domestic":
        return _domestic_time_valid(out_dep, ret_arr)
    return True


def _search_dates_route(
    origin: str,
    dest: str,
    start_date: str,
    end_date: str,
    trip_duration: int,
    max_stops: str,
) -> list[DatePrice]:
    try:
        origin_airport = resolve_airport(origin)
        dest_airport = resolve_airport(dest)
        stops = parse_max_stops(max_stops)
        seat = parse_cabin_class("ECONOMY")
        exclude_airlines = parse_airlines(EXCLUDED_AIRLINES)

        segments, trip_type = build_date_search_segments(
            origin=origin_airport,
            destination=dest_airport,
            start_date=start_date,
            trip_duration=trip_duration,
            is_round_trip=True,
        )
        filters = DateSearchFilters(
            trip_type=trip_type,
            passenger_info=PassengerInfo(adults=1),
            flight_segments=segments,
            stops=stops,
            seat_type=seat,
            airlines_exclude=exclude_airlines,
            from_date=start_date,
            to_date=end_date,
            duration=trip_duration,
        )

        searcher = _get_dates_searcher()
        results = None
        for attempt in range(MAX_RETRIES):
            results = searcher.search(filters)
            if results:
                break
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))

        if not results:
            with _stats_lock:
                _stats["dates_empty"] += 1
            return []

        with _stats_lock:
            _stats["dates_ok"] += 1
        return results
    except Exception as exc:
        with _stats_lock:
            _stats["errors"] += 1
        log.warning(
            "Date search failed %s→%s duration=%d: %s",
            origin,
            dest,
            trip_duration,
            exc,
        )
        return []


def _date_pairs_from_results(
    results: list[DatePrice],
    origin: str,
    dest: str,
    r_type: str,
) -> list[tuple[str, str, str, str, float]]:
    """Return (origin, dest, out_date, ret_date, price) candidates."""
    pairs: list[tuple[str, str, str, str, float]] = []
    for item in results:
        if item.price is None:
            continue
        if len(item.date) < 2:
            continue
        out_dt, ret_dt = item.date[0], item.date[1]
        if r_type == "domestic" and not _domestic_date_pair_valid(out_dt, ret_dt):
            continue
        pairs.append(
            (
                origin,
                dest,
                out_dt.strftime("%Y-%m-%d"),
                ret_dt.strftime("%Y-%m-%d"),
                float(item.price),
            )
        )
    return pairs


def _phase1_shortlist(
    region_name: str,
    config: dict,
    *,
    dom_start: str,
    dom_end: str,
    int_start: str,
    int_end: str,
    is_test: bool,
) -> list[tuple[str, str, str, str]]:
    r_type = config.get("type", "domestic")
    max_stops = config["max_stops"]
    start_date = dom_start if r_type == "domestic" else int_start
    end_date = dom_end if r_type == "domestic" else int_end
    durations = DOMESTIC_TRIP_DURATIONS if r_type == "domestic" else INTERNATIONAL_TRIP_DURATIONS

    if is_test:
        # Narrow window for smoke tests.
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = (start_dt + timedelta(days=7)).strftime("%Y-%m-%d")

    candidates: list[tuple[str, str, str, str, float]] = []
    dates_calls = 0

    for origin in ORIGINS:
        for dest in config["destinations"]:
            for duration in durations:
                results = _search_dates_route(
                    origin, dest, start_date, end_date, duration, max_stops
                )
                dates_calls += 1
                candidates.extend(_date_pairs_from_results(results, origin, dest, r_type))

    # Deduplicate by route+dates, keep lowest price per pair.
    best: dict[tuple[str, str, str, str], float] = {}
    for origin, dest, out_d, ret_d, price in candidates:
        key = (origin, dest, out_d, ret_d)
        if key not in best or price < best[key]:
            best[key] = price

    ranked = sorted(
        [(origin, dest, out_d, ret_d, best[(origin, dest, out_d, ret_d)]) for origin, dest, out_d, ret_d in best],
        key=lambda row: row[4],
    )
    limit = SHORTLIST_SIZE_TEST if is_test else SHORTLIST_SIZE
    shortlist = [(o, d, out_d, ret_d) for o, d, out_d, ret_d, _ in ranked[:limit]]

    log.info(
        "%s phase 1: %d date API calls → %d candidates → shortlist %d",
        region_name,
        dates_calls,
        len(best),
        len(shortlist),
    )
    return shortlist


def _search_pair(
    origin: str,
    dest: str,
    out_date_str: str,
    ret_date_str: str,
    max_stops: str,
    r_type: str,
) -> list[dict]:
    matches: list[dict] = []
    try:
        origin_airport = resolve_airport(origin)
        dest_airport = resolve_airport(dest)
        stops = parse_max_stops(max_stops)
        seat = parse_cabin_class("ECONOMY")
        exclude_airlines = parse_airlines(EXCLUDED_AIRLINES)

        segments, trip_type = build_flight_segments(
            origin=origin_airport,
            destination=dest_airport,
            departure_date=out_date_str,
            return_date=ret_date_str,
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

        searcher = _get_flight_searcher()
        results = None
        for attempt in range(MAX_RETRIES):
            results = searcher.search(filters)
            if results:
                break
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))

        if not results:
            with _stats_lock:
                _stats["flights_empty"] += 1
            return matches

        for result in results:
            booking_url = searcher.build_flight_booking_url(result)
            flight = serialize_flight_result(result, booking_url=booking_url)
            if not _flight_matches(flight, r_type):
                continue
            airline_name = flight["outbound"]["legs"][0]["airline"]["name"]
            matches.append(
                {
                    "origin": origin,
                    "destination": dest,
                    "out_date": out_date_str,
                    "ret_date": ret_date_str,
                    "price": flight["price"],
                    "airline": airline_name,
                    "out_dep": flight["outbound"]["legs"][0]["departure_time"],
                    "ret_arr": flight["return"]["legs"][-1]["arrival_time"],
                    "url": flight.get("booking_url") or "",
                }
            )

        with _stats_lock:
            _stats["flights_ok"] += 1
    except Exception as exc:
        with _stats_lock:
            _stats["errors"] += 1
        log.warning(
            "Flight search failed %s→%s %s/%s: %s",
            origin,
            dest,
            out_date_str,
            ret_date_str,
            exc,
        )
    return matches


def _sort_region(flights: list[dict]) -> list[dict]:
    priced = [f for f in flights if f.get("price") is not None]
    priced.sort(key=lambda row: row["price"])
    return priced


def main() -> int:
    is_test = "--test" in sys.argv
    force = "--force" in sys.argv

    all_results = {region: [] for region in REGIONS}
    if os.path.exists(OUTPUT_JSON) and not force:
        try:
            with open(OUTPUT_JSON, encoding="utf-8") as handle:
                existing = json.load(handle)
            if isinstance(existing, dict):
                for region_name in REGIONS:
                    if existing.get(region_name):
                        all_results[region_name] = existing[region_name]
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not load existing results for resume: %s", exc)

    log.info(
        "Starting two-phase search (test=%s, resume=%s, shortlist=%d)",
        is_test,
        not force,
        SHORTLIST_SIZE_TEST if is_test else SHORTLIST_SIZE,
    )

    today = datetime.now()
    dom_start = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    dom_end = (today + timedelta(days=74)).strftime("%Y-%m-%d")
    int_start = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    int_end = (today + timedelta(days=42)).strftime("%Y-%m-%d")

    for region_name, config in REGIONS.items():
        if all_results[region_name] and not force:
            log.info(
                "Skipping %s — already have %d flights (use --force to re-search)",
                region_name,
                len(all_results[region_name]),
            )
            continue

        r_type = config.get("type", "domestic")
        log.info("=== Region: %s ===", region_name)

        shortlist = _phase1_shortlist(
            region_name,
            config,
            dom_start=dom_start,
            dom_end=dom_end,
            int_start=int_start,
            int_end=int_end,
            is_test=is_test,
        )

        if not shortlist:
            log.warning("%s: empty shortlist, skipping phase 2", region_name)
            atomic_write_json(OUTPUT_JSON, all_results)
            continue

        log.info("%s phase 2: %d flight searches", region_name, len(shortlist))
        for i, (origin, dest, out_date, ret_date) in enumerate(shortlist, start=1):
            flights = _search_pair(origin, dest, out_date, ret_date, config["max_stops"], r_type)
            all_results[region_name].extend(flights)
            if i % 5 == 0 or i == len(shortlist):
                log.info(
                    "%s phase 2: %d/%d pairs searched, %d flights collected",
                    region_name,
                    i,
                    len(shortlist),
                    len(all_results[region_name]),
                )

        all_results[region_name] = _sort_region(all_results[region_name])
        atomic_write_json(OUTPUT_JSON, all_results)
        log.info("Checkpoint %s: %d flights", region_name, len(all_results[region_name]))

    log.info(
        "Search complete — dates_ok=%d dates_empty=%d flights_ok=%d flights_empty=%d errors=%d",
        _stats["dates_ok"],
        _stats["dates_empty"],
        _stats["flights_ok"],
        _stats["flights_empty"],
        _stats["errors"],
    )
    for region_name in REGIONS:
        log.info("%s: %d matching flights", region_name, len(all_results[region_name]))
    return 0 if _stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
