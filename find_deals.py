"""Premium-cabin deal discovery for Fli-Tracker.

Two-phase pipeline (SearchDates → SearchFlights) for non-economy cabins on a
rotating subset of curated worldwide destinations from SLC/PVU.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
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
    EXCLUDED_AIRLINES,
    PREMIUM_CABIN_CLASSES,
    PREMIUM_DATE_OFFSET_END,
    PREMIUM_DATE_OFFSET_START,
    PREMIUM_DEAL_DESTINATIONS,
    PREMIUM_DEAL_MAX_PRICE,
    PREMIUM_DEAL_ORIGINS,
    PREMIUM_DEAL_OUTPUT_JSON,
    PREMIUM_DESTINATIONS_PER_RUN,
    PREMIUM_DESTINATIONS_PER_RUN_TEST,
    PREMIUM_GLOBAL_TOP_N,
    PREMIUM_MAX_DEALS_PER_DEST,
    PREMIUM_MAX_STOPS,
    PREMIUM_SHORTLIST_SIZE,
    PREMIUM_SHORTLIST_SIZE_TEST,
    PREMIUM_TRIP_DURATION,
)
from tracker_io import atomic_write_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("find_deals")

_flight_searcher: SearchFlights | None = None
_dates_searcher: SearchDates | None = None
_searcher_lock = Lock()
_stats = {
    "dates_ok": 0,
    "dates_empty": 0,
    "flights_ok": 0,
    "flights_empty": 0,
    "flights_filtered": 0,
    "errors": 0,
}
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


def price_threshold(dest_type: str, cabin: str) -> float:
    """Return max round-trip cash price (USD) for a destination type and cabin."""
    thresholds = PREMIUM_DEAL_MAX_PRICE.get(dest_type, PREMIUM_DEAL_MAX_PRICE["international"])
    return float(thresholds.get(cabin, thresholds.get("BUSINESS", 2000)))


def passes_threshold(price: float | None, dest_type: str, cabin: str) -> bool:
    """Return True when price is at or below the configured cabin threshold."""
    if price is None:
        return False
    return float(price) <= price_threshold(dest_type, cabin)


def destinations_for_run(*, is_test: bool) -> list[dict[str, str]]:
    """Rotate a daily batch so full destination set is covered over multiple runs."""
    all_dests = list(PREMIUM_DEAL_DESTINATIONS)
    per_run = PREMIUM_DESTINATIONS_PER_RUN_TEST if is_test else PREMIUM_DESTINATIONS_PER_RUN
    if len(all_dests) <= per_run:
        return all_dests

    batches = math.ceil(len(all_dests) / per_run)
    batch_idx = datetime.now().timetuple().tm_yday % batches
    start = batch_idx * per_run
    return all_dests[start : start + per_run]


def _load_prior() -> dict:
    if not os.path.exists(PREMIUM_DEAL_OUTPUT_JSON):
        return {"deals": [], "searched_destinations": []}
    try:
        with open(PREMIUM_DEAL_OUTPUT_JSON, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not load prior %s: %s", PREMIUM_DEAL_OUTPUT_JSON, exc)
        return {"deals": [], "searched_destinations": []}
    if not isinstance(data, dict):
        return {"deals": [], "searched_destinations": []}
    deals = data.get("deals", [])
    if not isinstance(deals, list):
        deals = []
    valid = [row for row in deals if isinstance(row, dict)]
    searched = data.get("searched_destinations", [])
    if not isinstance(searched, list):
        searched = []
    return {"deals": valid, "searched_destinations": searched}


def _count_deals(deals: list[dict]) -> int:
    return len(deals)


def _deal_key(deal: dict) -> tuple:
    return (
        deal.get("origin", ""),
        deal.get("airport", deal.get("destination", "")),
        deal.get("cabin", ""),
        deal.get("out_date", ""),
        deal.get("ret_date", ""),
        deal.get("airline", ""),
    )


def merge_rotated_results(
    prior_deals: list[dict],
    new_deals: list[dict],
    searched_airports: set[str],
) -> list[dict]:
    """Keep stale deals for destinations not searched today; replace searched ones."""
    kept = [
        deal
        for deal in prior_deals
        if deal.get("airport", deal.get("destination", "")) not in searched_airports
    ]
    merged = kept + new_deals
    return rank_deals(merged)


def rank_deals(deals: list[dict]) -> list[dict]:
    """Sort by price; cap per destination and global top N."""
    priced = [d for d in deals if d.get("price") is not None]
    priced.sort(key=lambda row: float(row["price"]))

    per_dest: dict[tuple[str, str], int] = {}
    capped: list[dict] = []
    for deal in priced:
        key = (deal.get("airport", deal.get("destination", "")), deal.get("cabin", ""))
        count = per_dest.get(key, 0)
        if count >= PREMIUM_MAX_DEALS_PER_DEST:
            continue
        per_dest[key] = count + 1
        capped.append(deal)
        if len(capped) >= PREMIUM_GLOBAL_TOP_N:
            break
    return capped


def _search_dates_route(
    origin: str,
    dest: str,
    start_date: str,
    end_date: str,
    trip_duration: int,
    cabin: str,
) -> list[DatePrice]:
    try:
        origin_airport = resolve_airport(origin)
        dest_airport = resolve_airport(dest)
        stops = parse_max_stops(PREMIUM_MAX_STOPS)
        seat = parse_cabin_class(cabin)
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
        results: list[DatePrice] | None = None
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
            "Date search failed %s→%s cabin=%s: %s",
            origin,
            dest,
            cabin,
            exc,
        )
        return []


def _date_pairs_from_results(
    results: list[DatePrice],
    origin: str,
    dest: str,
    dest_type: str,
    cabin: str,
) -> list[tuple[str, str, str, str, float]]:
    pairs: list[tuple[str, str, str, str, float]] = []
    for item in results:
        if item.price is None:
            continue
        if not passes_threshold(item.price, dest_type, cabin):
            continue
        if len(item.date) < 2:
            continue
        out_dt, ret_dt = item.date[0], item.date[1]
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
    dest_info: dict[str, str],
    *,
    start_date: str,
    end_date: str,
    is_test: bool,
) -> list[tuple[str, str, str, str, str]]:
    """Return (origin, dest, out_date, ret_date, cabin) pairs for phase 2."""
    dest = dest_info["airport"]
    dest_type = dest_info.get("type", "international")
    shortlist_limit = PREMIUM_SHORTLIST_SIZE_TEST if is_test else PREMIUM_SHORTLIST_SIZE

    candidates: list[tuple[str, str, str, str, str, float]] = []
    dates_calls = 0

    for cabin in PREMIUM_CABIN_CLASSES:
        # Phase 1 uses SLC only to cap API volume; phase 2 tries all origins.
        results = _search_dates_route(
            "SLC",
            dest,
            start_date,
            end_date,
            PREMIUM_TRIP_DURATION,
            cabin,
        )
        dates_calls += 1
        for origin, _dest, out_d, ret_d, price in _date_pairs_from_results(
            results, "SLC", dest, dest_type, cabin
        ):
            candidates.append((origin, dest, out_d, ret_d, cabin, price))

    best: dict[tuple[str, str, str, str, str], float] = {}
    for origin, d, out_d, ret_d, cabin, price in candidates:
        key = (origin, d, out_d, ret_d, cabin)
        if key not in best or price < best[key]:
            best[key] = price

    ranked = sorted(
        [(k[0], k[1], k[2], k[3], k[4], best[k]) for k in best],
        key=lambda row: row[5],
    )
    shortlist = [
        (o, d, out_d, ret_d, cabin)
        for o, d, out_d, ret_d, cabin, _ in ranked[:shortlist_limit]
    ]

    log.info(
        "%s phase 1: %d date API calls → %d candidates → shortlist %d",
        dest,
        dates_calls,
        len(best),
        len(shortlist),
    )
    return shortlist


def _deal_from_flight(
    flight: dict,
    *,
    origin: str,
    dest_info: dict[str, str],
    cabin: str,
    out_date: str,
    ret_date: str,
) -> dict | None:
    price = flight.get("price")
    dest_type = dest_info.get("type", "international")
    if not passes_threshold(price, dest_type, cabin):
        return None

    try:
        airline_name = flight["outbound"]["legs"][0]["airline"]["name"]
        out_dep = flight["outbound"]["legs"][0]["departure_time"]
        ret_arr = flight["return"]["legs"][-1]["arrival_time"]
    except (KeyError, TypeError, IndexError):
        return None

    cabin_label = cabin.replace("_", " ").title()
    return {
        "origin": origin,
        "destination": dest_info["label"],
        "airport": dest_info["airport"],
        "region_label": dest_info.get("region_label", ""),
        "type": dest_type,
        "is_domestic": dest_type == "domestic",
        "cabin": cabin_label,
        "price": int(float(price)),
        "out_date": out_date,
        "ret_date": ret_date,
        "airline": airline_name,
        "duration": flight.get("duration"),
        "stops": flight.get("stops"),
        "booking_url": flight.get("booking_url") or flight.get("url") or "",
        "out_dep": out_dep,
        "ret_arr": ret_arr,
    }


def _search_pair(
    origin: str,
    dest_info: dict[str, str],
    out_date_str: str,
    ret_date_str: str,
    cabin: str,
) -> list[dict]:
    dest = dest_info["airport"]
    matches: list[dict] = []
    try:
        origin_airport = resolve_airport(origin)
        dest_airport = resolve_airport(dest)
        stops = parse_max_stops(PREMIUM_MAX_STOPS)
        seat = parse_cabin_class(cabin)
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
            try:
                results = searcher.search(filters)
                break
            except Exception as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                else:
                    raise exc

        if not results:
            with _stats_lock:
                _stats["flights_empty"] += 1
            return matches

        for result in results:
            booking_url = searcher.build_flight_booking_url(result)
            flight = serialize_flight_result(result, booking_url=booking_url)
            deal = _deal_from_flight(
                flight,
                origin=origin,
                dest_info=dest_info,
                cabin=cabin,
                out_date=out_date_str,
                ret_date=ret_date_str,
            )
            if deal is None:
                with _stats_lock:
                    _stats["flights_filtered"] += 1
                continue
            matches.append(deal)

        if matches:
            with _stats_lock:
                _stats["flights_ok"] += 1
    except Exception as exc:
        with _stats_lock:
            _stats["errors"] += 1
        log.warning(
            "Flight search failed %s→%s %s/%s cabin=%s: %s",
            origin,
            dest,
            out_date_str,
            ret_date_str,
            cabin,
            exc,
        )
    return matches


def estimate_api_calls(dest_count: int, *, is_test: bool) -> int:
    """Rough API call budget for a run."""
    cabins = len(PREMIUM_CABIN_CLASSES)
    shortlist = PREMIUM_SHORTLIST_SIZE_TEST if is_test else PREMIUM_SHORTLIST_SIZE
    origins = len(PREMIUM_DEAL_ORIGINS)
    phase1 = dest_count * cabins
    phase2 = dest_count * shortlist * origins
    return phase1 + phase2


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Premium-cabin deal discovery (SearchDates → SearchFlights).",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Smoke test: 3 destinations, minimal shortlist.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore prior deals for searched destinations (full refresh of today's batch).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run premium-cabin deal discovery for today's destination batch."""
    args = _parse_args(argv)
    prior = _load_prior()
    prior_deals = prior["deals"]

    if args.force and _count_deals(prior_deals) == 0:
        prior_deals = []

    today_dests = destinations_for_run(is_test=args.test)
    searched_airports = {d["airport"] for d in today_dests}

    today = datetime.now()
    start_date = (today + timedelta(days=PREMIUM_DATE_OFFSET_START)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=PREMIUM_DATE_OFFSET_END)).strftime("%Y-%m-%d")
    if args.test:
        end_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=14)
        end_date = end_dt.strftime("%Y-%m-%d")

    est_calls = estimate_api_calls(len(today_dests), is_test=args.test)
    log.info(
        "Starting premium deal search (test=%s, destinations=%d, est_api_calls=%d)",
        args.test,
        len(today_dests),
        est_calls,
    )
    log.info(
        "Date window %s → %s, trip %d nights, cabins=%s",
        start_date,
        end_date,
        PREMIUM_TRIP_DURATION,
        ", ".join(PREMIUM_CABIN_CLASSES),
    )

    new_deals: list[dict] = []
    for dest_info in today_dests:
        airport = dest_info["airport"]
        log.info("=== Destination: %s (%s) ===", dest_info["label"], airport)

        shortlist = _phase1_shortlist(
            dest_info,
            start_date=start_date,
            end_date=end_date,
            is_test=args.test,
        )
        if not shortlist:
            log.warning("%s: empty shortlist, skipping phase 2", airport)
            continue

        dest_deals: list[dict] = []
        flight_calls = 0
        for _slc_origin, _dest, out_date, ret_date, cabin in shortlist:
            for origin in PREMIUM_DEAL_ORIGINS:
                flights = _search_pair(origin, dest_info, out_date, ret_date, cabin)
                flight_calls += 1
                dest_deals.extend(flights)

        dest_deals = rank_deals(dest_deals)
        new_deals.extend(dest_deals)
        log.info(
            "%s phase 2: %d flight searches → %d deals under threshold",
            airport,
            flight_calls,
            len(dest_deals),
        )

    if args.force:
        merged = rank_deals(new_deals)
    else:
        merged = merge_rotated_results(prior_deals, new_deals, searched_airports)

    payload = {
        "last_run": today.strftime("%Y-%m-%d"),
        "origins": PREMIUM_DEAL_ORIGINS,
        "searched_destinations": sorted(searched_airports),
        "deals": merged,
    }

    log.info(
        "Search complete — dates_ok=%d dates_empty=%d flights_ok=%d flights_empty=%d "
        "flights_filtered=%d errors=%d deals=%d",
        _stats["dates_ok"],
        _stats["dates_empty"],
        _stats["flights_ok"],
        _stats["flights_empty"],
        _stats["flights_filtered"],
        _stats["errors"],
        len(merged),
    )

    if len(new_deals) == 0 and _count_deals(prior_deals) > 0:
        log.warning(
            "Today's batch returned zero new deals — preserving prior %s (%d deals)",
            PREMIUM_DEAL_OUTPUT_JSON,
            _count_deals(prior_deals),
        )
        payload["deals"] = prior_deals
        payload["searched_destinations"] = prior.get("searched_destinations", [])

    atomic_write_json(PREMIUM_DEAL_OUTPUT_JSON, payload)

    if len(payload["deals"]) == 0 and _stats["errors"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
