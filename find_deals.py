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
    google_flights_url,
    parse_airlines,
    parse_cabin_class,
    parse_max_stops,
    resolve_airport,
)
from fli.models import DateSearchFilters, FlightSearchFilters, PassengerInfo
from fli.search import SearchDates, SearchFlights
from fli.search.dates import DatePrice
from tracker_config import (
    CHASE_POINTS_CENT_VALUE,
    EXCLUDED_AIRLINES,
    PREMIUM_CABIN_CLASSES,
    PREMIUM_DATE_OFFSET_END,
    PREMIUM_DATE_OFFSET_START,
    PREMIUM_DEAL_DESTINATIONS,
    PREMIUM_DEAL_MAX_POINTS,
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
    PREMIUM_TRIP_DURATIONS,
    PREMIUM_TRIP_DURATIONS_PER_RUN,
    PREMIUM_TRIP_DURATIONS_PER_RUN_TEST,
)
from tracker_io import atomic_write_json

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import seats_aero_client
from seats_aero_client import AwardAvailability, lookup_award

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


def points_threshold(dest_type: str, cabin: str) -> int:
    """Return max round-trip award points for a destination type and cabin."""
    thresholds = PREMIUM_DEAL_MAX_POINTS.get(dest_type, PREMIUM_DEAL_MAX_POINTS["international"])
    return int(thresholds.get(cabin, thresholds.get("BUSINESS", 200_000)))


def estimate_chase_points(cash_price: float | int | None) -> int | None:
    """Estimate Chase Travel Portal points for a cash fare (Sapphire Preferred 1.25¢)."""
    if cash_price is None:
        return None
    return int((float(cash_price) * 100) / CHASE_POINTS_CENT_VALUE)


def passes_threshold(price: float | None, dest_type: str, cabin: str) -> bool:
    """Return True when price is at or below the configured cabin threshold."""
    if price is None:
        return False
    return float(price) <= price_threshold(dest_type, cabin)


def passes_points_threshold(points: int | None, dest_type: str, cabin: str) -> bool:
    """Return True when award points are at or below the configured cabin threshold."""
    if points is None:
        return False
    return int(points) <= points_threshold(dest_type, cabin)


def passes_deal_threshold(
    price: float | None,
    points: int | None,
    dest_type: str,
    cabin: str,
) -> bool:
    """Deal qualifies when cash OR award points meet cabin thresholds."""
    return passes_threshold(price, dest_type, cabin) or passes_points_threshold(
        points, dest_type, cabin
    )


def payment_type_for_deal(
    price: float | None,
    points: int | None,
    *,
    points_from_award: bool,
) -> str:
    """Classify how the fare can be booked: cash, points, or both."""
    has_cash = price is not None
    has_award = points is not None and points_from_award
    has_estimate = points is not None and not points_from_award
    if has_cash and has_award:
        return "both"
    if has_award:
        return "points"
    if has_cash and has_estimate:
        return "both"
    if has_estimate:
        return "points"
    return "cash"


def durations_for_run(*, is_test: bool) -> list[int]:
    """Rotate trip durations daily so the full set is covered over multiple runs."""
    all_durations = list(PREMIUM_TRIP_DURATIONS)
    per_run = PREMIUM_TRIP_DURATIONS_PER_RUN_TEST if is_test else PREMIUM_TRIP_DURATIONS_PER_RUN
    if len(all_durations) <= per_run:
        return all_durations

    batches = math.ceil(len(all_durations) / per_run)
    batch_idx = datetime.now().timetuple().tm_yday % batches
    start = batch_idx * per_run
    return all_durations[start : start + per_run]


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


def is_valid_deep_booking_url(url: str | None) -> bool:
    """Return whether URL is a Google Flights itinerary deep link (tfs= booking page)."""
    if not url:
        return False
    cleaned = str(url).strip()
    return cleaned.startswith("https://") and "tfs=" in cleaned


def deal_has_cash_price(deal: dict) -> bool:
    """Return True when the deal includes a round-trip cash fare."""
    return deal.get("price") is not None


def deal_rank_tier(deal: dict) -> int:
    """Lower tier sorts first: cash+book link, cash only, points+search, other."""
    has_cash = deal_has_cash_price(deal)
    deep_url = deal.get("booking_url") or ""
    search_url = deal.get("google_flights_url") or ""
    if has_cash and is_valid_deep_booking_url(deep_url):
        return 0
    if has_cash:
        return 1
    if deal.get("points") is not None and (search_url or deep_url):
        return 2
    return 3


def _deal_sort_value(deal: dict) -> float:
    """Lower is better; cash price preferred, else points converted to cash equiv."""
    price = deal.get("price")
    if price is not None:
        return float(price)
    points = deal.get("points")
    if points is not None:
        return float(points) * CHASE_POINTS_CENT_VALUE / 100.0
    return float("inf")


def deal_sort_key(deal: dict) -> tuple[int, float]:
    """Sort key: bookable cash first, then by best value within tier."""
    return (deal_rank_tier(deal), _deal_sort_value(deal))


def rank_deals(deals: list[dict]) -> list[dict]:
    """Sort by bookable cash first, then best value; cap per destination and global top N."""
    priced = [d for d in deals if d.get("price") is not None or d.get("points") is not None]
    priced.sort(key=deal_sort_key)

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
    trip_duration: int,
) -> list[tuple[str, str, str, str, float, int]]:
    pairs: list[tuple[str, str, str, str, float, int]] = []
    for item in results:
        if item.price is None:
            continue
        chase_pts = estimate_chase_points(item.price)
        if not passes_deal_threshold(item.price, chase_pts, dest_type, cabin):
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
                trip_duration,
            )
        )
    return pairs


def _fetch_seats_aero_award(
    origin: str,
    dest: str,
    out_date: str,
    ret_date: str,
    cabin: str,
    *,
    award_cache: list[AwardAvailability] | None,
) -> tuple[int | None, str | None]:
    """Award points from pre-fetched seats.aero cache (round-trip estimate).

    Cached search is per departure date one-way; we use lowest outbound cost × 2.
    ``ret_date`` is unused today — return-leg pricing may differ (known limitation).
    """
    if not award_cache:
        return None, None
    row = lookup_award(
        award_cache,
        origin=origin,
        dest=dest,
        out_date=out_date,
        cabin=cabin,
    )
    if row is None:
        return None, None
    return row.points_round_trip_estimate, row.mileage_program


def _prefetch_seats_aero_for_dest(
    dest_airport: str,
    start_date: str,
    end_date: str,
) -> list[AwardAvailability]:
    """One cached search per destination (all origins + premium cabins)."""
    if not seats_aero_client.is_enabled():
        return []
    rows = seats_aero_client.cached_search_destination(
        list(PREMIUM_DEAL_ORIGINS),
        dest_airport,
        start_date,
        end_date,
    )
    if rows:
        log.info(
            "%s seats.aero: %d award rows (usage %s)",
            dest_airport,
            len(rows),
            seats_aero_client.get_usage_summary(),
        )
    return rows


def _award_only_deals_from_cache(
    dest_info: dict[str, str],
    award_cache: list[AwardAvailability],
    trip_durations: list[int],
    *,
    existing_keys: set[tuple],
) -> list[dict]:
    """Create points-only deals when seats.aero has awards under threshold."""
    dest_type = dest_info.get("type", "international")
    dest_airport = dest_info["airport"]
    deals: list[dict] = []

    by_key: dict[tuple[str, str, str], AwardAvailability] = {}
    for row in award_cache:
        if row.destination != dest_airport:
            continue
        key = (row.origin, row.out_date, row.cabin)
        if key not in by_key or row.points_one_way < by_key[key].points_one_way:
            by_key[key] = row

    for (origin, out_date, cabin), row in by_key.items():
        points = row.points_round_trip_estimate
        if not passes_points_threshold(points, dest_type, cabin):
            continue
        out_dt = datetime.strptime(out_date, "%Y-%m-%d")
        for duration in trip_durations:
            ret_dt = out_dt + timedelta(days=duration)
            ret_date = ret_dt.strftime("%Y-%m-%d")
            deal_key = (origin, dest_airport, cabin, out_date, ret_date, "")
            if deal_key in existing_keys:
                continue
            cabin_label = cabin.replace("_", " ").title()
            airline = row.airlines.split(",")[0].strip() if row.airlines else row.mileage_program
            deals.append(
                {
                    "origin": origin,
                    "destination": dest_info["label"],
                    "airport": dest_airport,
                    "region_label": dest_info.get("region_label", ""),
                    "type": dest_type,
                    "is_domestic": dest_type == "domestic",
                    "cabin": cabin_label,
                    "price": None,
                    "points": points,
                    "points_source": "seats_aero",
                    "mileage_program": row.mileage_program,
                    "paymentType": "points",
                    "hasCashPrice": False,
                    "isRoundTrip": True,
                    "trip_duration": duration,
                    "out_date": out_date,
                    "ret_date": ret_date,
                    "airline": airline,
                    "duration": None,
                    "stops": None,
                    "booking_url": "",
                    "google_flights_url": google_flights_url(
                        origin, dest_airport, out_date, ret_date
                    ),
                    "out_dep": None,
                    "ret_arr": None,
                }
            )
    return deals


def _phase1_shortlist(
    dest_info: dict[str, str],
    *,
    start_date: str,
    end_date: str,
    is_test: bool,
) -> list[tuple[str, str, str, str, str, int]]:
    """Return (origin, dest, out_date, ret_date, cabin, trip_duration) pairs for phase 2."""
    dest = dest_info["airport"]
    dest_type = dest_info.get("type", "international")
    shortlist_limit = PREMIUM_SHORTLIST_SIZE_TEST if is_test else PREMIUM_SHORTLIST_SIZE
    trip_durations = durations_for_run(is_test=is_test)

    candidates: list[tuple[str, str, str, str, str, float, int]] = []
    dates_calls = 0

    for cabin in PREMIUM_CABIN_CLASSES:
        for trip_duration in trip_durations:
            # Phase 1 uses SLC only to cap API volume; phase 2 tries all origins.
            results = _search_dates_route(
                "SLC",
                dest,
                start_date,
                end_date,
                trip_duration,
                cabin,
            )
            dates_calls += 1
            for origin, _dest, out_d, ret_d, price, duration in _date_pairs_from_results(
                results, "SLC", dest, dest_type, cabin, trip_duration
            ):
                candidates.append((origin, dest, out_d, ret_d, cabin, price, duration))

    best: dict[tuple[str, str, str, str, str, int], float] = {}
    for origin, d, out_d, ret_d, cabin, price, duration in candidates:
        key = (origin, d, out_d, ret_d, cabin, duration)
        if key not in best or price < best[key]:
            best[key] = price

    ranked = sorted(
        [(k[0], k[1], k[2], k[3], k[4], k[5], best[k]) for k in best],
        key=lambda row: row[6],
    )
    shortlist = [
        (o, d, out_d, ret_d, cabin, duration)
        for o, d, out_d, ret_d, cabin, duration, _ in ranked[:shortlist_limit]
    ]

    log.info(
        "%s phase 1: %d date API calls (%d durations) → %d candidates → shortlist %d",
        dest,
        dates_calls,
        len(trip_durations),
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
    trip_duration: int,
    award_cache: list[AwardAvailability] | None = None,
) -> dict | None:
    price = flight.get("price")
    dest_type = dest_info.get("type", "international")

    award_points, mileage_program = _fetch_seats_aero_award(
        origin,
        dest_info["airport"],
        out_date,
        ret_date,
        cabin,
        award_cache=award_cache,
    )
    chase_points = estimate_chase_points(price)
    points = award_points if award_points is not None else chase_points
    points_from_award = award_points is not None

    if not passes_deal_threshold(price, points, dest_type, cabin):
        return None

    try:
        airline_name = flight["outbound"]["legs"][0]["airline"]["name"]
        out_dep = flight["outbound"]["legs"][0]["departure_time"]
        ret_arr = flight["return"]["legs"][-1]["arrival_time"]
    except (KeyError, TypeError, IndexError):
        return None

    cabin_label = cabin.replace("_", " ").title()
    deal_price = int(float(price)) if price is not None else None
    points_source = "seats_aero" if points_from_award else ("chase_estimate" if points else None)
    deep_booking_url = flight.get("booking_url") or flight.get("url") or ""
    deal: dict = {
        "origin": origin,
        "destination": dest_info["label"],
        "airport": dest_info["airport"],
        "region_label": dest_info.get("region_label", ""),
        "type": dest_type,
        "is_domestic": dest_type == "domestic",
        "cabin": cabin_label,
        "price": deal_price,
        "points": points,
        "points_source": points_source,
        "paymentType": payment_type_for_deal(
            float(price) if price is not None else None,
            points,
            points_from_award=points_from_award,
        ),
        "hasCashPrice": deal_price is not None,
        "isRoundTrip": True,
        "trip_duration": trip_duration,
        "out_date": out_date,
        "ret_date": ret_date,
        "airline": airline_name,
        "duration": flight.get("duration"),
        "stops": flight.get("stops"),
        "booking_url": deep_booking_url,
        "google_flights_url": (
            ""
            if is_valid_deep_booking_url(deep_booking_url)
            else google_flights_url(origin, dest_info["airport"], out_date, ret_date)
        ),
        "out_dep": out_dep,
        "ret_arr": ret_arr,
    }
    if mileage_program:
        deal["mileage_program"] = mileage_program
    return deal


def _search_pair(
    origin: str,
    dest_info: dict[str, str],
    out_date_str: str,
    ret_date_str: str,
    cabin: str,
    trip_duration: int,
    *,
    award_cache: list[AwardAvailability] | None = None,
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
                trip_duration=trip_duration,
                award_cache=award_cache,
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
    durations = PREMIUM_TRIP_DURATIONS_PER_RUN_TEST if is_test else PREMIUM_TRIP_DURATIONS_PER_RUN
    shortlist = PREMIUM_SHORTLIST_SIZE_TEST if is_test else PREMIUM_SHORTLIST_SIZE
    origins = len(PREMIUM_DEAL_ORIGINS)
    phase1 = dest_count * cabins * durations
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

    if seats_aero_client.is_enabled():
        seats_aero_client.begin_run()
        log.info("seats.aero enabled (budget %s)", seats_aero_client.get_usage_summary())
    else:
        log.info("seats.aero disabled — award points use Chase estimate when cash fares exist")

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

    trip_durations = durations_for_run(is_test=args.test)
    est_calls = estimate_api_calls(len(today_dests), is_test=args.test)
    log.info(
        "Starting premium deal search (test=%s, destinations=%d, est_api_calls=%d)",
        args.test,
        len(today_dests),
        est_calls,
    )
    log.info(
        "Date window %s → %s, trip durations=%s nights, cabins=%s",
        start_date,
        end_date,
        trip_durations,
        ", ".join(PREMIUM_CABIN_CLASSES),
    )

    new_deals: list[dict] = []
    for dest_info in today_dests:
        airport = dest_info["airport"]
        log.info("=== Destination: %s (%s) ===", dest_info["label"], airport)

        award_cache = _prefetch_seats_aero_for_dest(airport, start_date, end_date)

        shortlist = _phase1_shortlist(
            dest_info,
            start_date=start_date,
            end_date=end_date,
            is_test=args.test,
        )
        if not shortlist:
            log.warning("%s: empty shortlist, skipping phase 2", airport)
            if award_cache:
                award_only = _award_only_deals_from_cache(
                    dest_info,
                    award_cache,
                    trip_durations,
                    existing_keys=set(),
                )
                if award_only:
                    new_deals.extend(rank_deals(award_only))
                    log.info("%s: %d award-only deals from seats.aero", airport, len(award_only))
            continue

        dest_deals: list[dict] = []
        flight_calls = 0
        for _slc_origin, _dest, out_date, ret_date, cabin, trip_duration in shortlist:
            for origin in PREMIUM_DEAL_ORIGINS:
                flights = _search_pair(
                    origin,
                    dest_info,
                    out_date,
                    ret_date,
                    cabin,
                    trip_duration,
                    award_cache=award_cache,
                )
                flight_calls += 1
                dest_deals.extend(flights)

        existing_keys = {_deal_key(d) for d in dest_deals}
        if award_cache and not dest_deals:
            award_only = _award_only_deals_from_cache(
                dest_info,
                award_cache,
                trip_durations,
                existing_keys=existing_keys,
            )
            dest_deals.extend(award_only)
            if award_only:
                log.info("%s: %d award-only deals from seats.aero", airport, len(award_only))

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
