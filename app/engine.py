"""Search engine — direct Python API calls to fli + hotels.

Calls fli's SearchFlights/SearchDates classes through a shared HTTP client
with connection pooling, rate limiting, and per-itinerary booking deep links.
"""

import asyncio
import json
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, AsyncGenerator, Optional

from fli.core import (
    build_date_search_segments,
    build_flight_segments,
    build_time_restrictions,
    parse_airlines,
    parse_alliances,
    parse_cabin_class,
    parse_max_stops,
    parse_sort_by,
)
from fli.models import (
    DateSearchFilters,
    FlightSearchFilters,
    LayoverRestrictions,
    PassengerInfo,
)
from fli.search import SearchDates, SearchFlights

from app.airport_data import iata_to_city
from app.tracker import get_refund_eligibility_by_code, TrackerDB
from tracker_config import EXCLUDED_AIRLINES

# Lazy import to avoid circular deps at import time
_hotels_core = None


def _get_hotels_core():
    global _hotels_core
    if _hotels_core is None:
        from app.hotels import search_hotels_core
        _hotels_core = search_hotels_core
    return _hotels_core


logger = logging.getLogger("engine")

# Shared instances — single HTTP client reused across all searches
_flight_search: SearchFlights | None = None
_date_search: SearchDates | None = None
_executor = ThreadPoolExecutor(max_workers=8)


@dataclass
class FlightSearchOptions:
    """Extended search knobs shared by sync, async, and SSE paths."""

    max_stops: str = "ANY"
    cabin_class: str = "ECONOMY"
    airline_filter: str | None = None
    exclude_airlines: list[str] | None = None
    apply_default_exclusions: bool = True
    airlines: list[str] | None = None
    alliance: list[str] | None = None
    exclude_alliance: list[str] | None = None
    departure_window: str | None = None
    min_layover: int | None = None
    max_layover: int | None = None
    sort_by: str = "CHEAPEST"
    currency: str = "USD"
    language: str = "en"
    country: str = "US"


def _merged_exclude_airlines(opts: FlightSearchOptions) -> list[str] | None:
    excluded: list[str] = []
    if opts.apply_default_exclusions:
        excluded.extend(EXCLUDED_AIRLINES)
    if opts.exclude_airlines:
        excluded.extend(opts.exclude_airlines)
    if not excluded:
        return None
    return list(dict.fromkeys(excluded))


def _attach_booking_url(
    searcher: SearchFlights,
    raw_flight: Any,
    flight_data: dict,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    opts: FlightSearchOptions,
) -> None:
    """Prefer per-itinerary tfs deep link; fall back to generic search URL."""
    try:
        booking_url = searcher.build_flight_booking_url(
            raw_flight,
            currency=opts.currency,
            language=opts.language,
            country=opts.country,
        )
        if booking_url:
            flight_data["booking_url"] = booking_url
            flight_data["url"] = booking_url
            return
    except Exception:
        pass
    fallback = _build_google_flights_url(origin, destination, departure_date, return_date)
    flight_data["url"] = fallback
    flight_data.setdefault("booking_url", fallback)


def _get_flight_search() -> SearchFlights:
    global _flight_search
    if _flight_search is None:
        _flight_search = SearchFlights()
    return _flight_search


def _get_date_search() -> SearchDates:
    global _date_search
    if _date_search is None:
        _date_search = SearchDates()
    return _date_search


# ── Flight Search (Direct API) ──────────────────────────────────────────────


def _search_flights_sync(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    max_stops: str = "ANY",
    cabin_class: str = "ECONOMY",
    airline_filter: str | None = None,
    options: FlightSearchOptions | None = None,
) -> list[dict]:
    """Synchronous flight search using fli's Python API directly."""
    opts = options or FlightSearchOptions(
        max_stops=max_stops,
        cabin_class=cabin_class,
        airline_filter=airline_filter,
    )
    if options is None:
        opts.max_stops = max_stops
        opts.cabin_class = cabin_class
        opts.airline_filter = airline_filter

    try:
        origin_airport = _resolve_airport_safe(origin)
        dest_airport = _resolve_airport_safe(destination)
        if not origin_airport or not dest_airport:
            return []

        stops = parse_max_stops(opts.max_stops)
        seat = parse_cabin_class(opts.cabin_class)
        time_restrictions = build_time_restrictions(departure_window=opts.departure_window)

        segments, trip_type = build_flight_segments(
            origin=origin_airport,
            destination=dest_airport,
            departure_date=departure_date,
            return_date=return_date,
            time_restrictions=time_restrictions,
        )

        layover_restrictions = None
        if opts.min_layover is not None or opts.max_layover is not None:
            layover_restrictions = LayoverRestrictions(
                min_duration=opts.min_layover,
                max_duration=opts.max_layover,
            )

        exclude_codes = _merged_exclude_airlines(opts)
        airlines_include = parse_airlines(opts.airlines) if opts.airlines else None
        airlines_exclude = parse_airlines(exclude_codes) if exclude_codes else None
        alliances = parse_alliances(opts.alliance) if opts.alliance else None
        alliances_exclude = parse_alliances(opts.exclude_alliance) if opts.exclude_alliance else None

        filters = FlightSearchFilters(
            trip_type=trip_type,
            passenger_info=PassengerInfo(adults=1),
            flight_segments=segments,
            stops=stops,
            seat_type=seat,
            airlines=airlines_include,
            airlines_exclude=airlines_exclude,
            alliances=alliances,
            alliances_exclude=alliances_exclude,
            layover_restrictions=layover_restrictions,
            sort_by=parse_sort_by(opts.sort_by),
        )

        searcher = _get_flight_search()
        results = searcher.search(
            filters,
            currency=opts.currency,
            language=opts.language,
            country=opts.country,
        )

        if not results:
            return []

        serialized = []
        is_round_trip = trip_type.name == "ROUND_TRIP"
        for raw in results:
            flight_data = _serialize_flight(raw, is_round_trip)
            if not flight_data:
                continue
            if opts.airline_filter and opts.airline_filter.lower() != "any":
                airline_name = flight_data.get("airline", "").lower()
                airline_label = flight_data.get("airline_name", "").lower()
                needle = opts.airline_filter.lower()
                if needle not in airline_name and needle not in airline_label:
                    continue
            _attach_booking_url(
                searcher,
                raw,
                flight_data,
                origin,
                destination,
                departure_date,
                return_date,
                opts,
            )
            flight_data["depart_date"] = departure_date
            flight_data["return_date"] = return_date
            serialized.append(flight_data)

        serialized.sort(key=lambda x: x.get("price") if x.get("price") is not None else float("inf"))

        if serialized:
            db = TrackerDB()
            cheapest = serialized[0]
            db.log_search(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                price=cheapest.get("price", 0),
                airline=cheapest.get("airline", ""),
            )
            percentiles = db.get_historical_percentiles(origin, destination)
            if percentiles:
                for f in serialized:
                    p = f.get("price", 0)
                    if p <= percentiles["great"]:
                        f["price_level"] = "Great"
                    elif p >= percentiles["high"]:
                        f["price_level"] = "High"
                    else:
                        f["price_level"] = "Typical"
            else:
                for f in serialized:
                    f["price_level"] = "Typical"

        return serialized

    except Exception as e:
        logger.warning(f"Flight search {origin}→{destination} on {departure_date}: {e}")
        return []

def _extract_layovers(legs) -> list[dict]:
    layovers = []
    if len(legs) > 1:
        for i in range(len(legs) - 1):
            arr = legs[i].arrival_datetime
            dep = legs[i+1].departure_datetime
            if arr and dep:
                duration_mins = int((dep - arr).total_seconds() / 60)
                layovers.append({
                    "airport": str(legs[i].arrival_airport.name),
                    "duration": duration_mins
                })
    return layovers

def _serialize_flight(flight, is_round_trip: bool = False) -> dict | None:
    """Serialize a fli FlightResult into a flat dict with refund eligibility."""
    try:
        result = None
        if isinstance(flight, tuple):
            # Round-trip: (outbound, return)
            if len(flight) >= 2 and is_round_trip:
                outbound, return_flight = flight[0], flight[1]
                if outbound.price is None:
                    return None
                out_leg = outbound.legs[0]
                ret_leg = return_flight.legs[-1]
                result = {
                    "price": outbound.price,
                    "currency": outbound.currency or "USD",
                    "airline": str(out_leg.airline.name).lstrip("_"),
                    "airline_name": _airline_display_name(out_leg.airline),
                    "flight_number": out_leg.flight_number or "",
                    "departure_time": out_leg.departure_datetime.strftime("%H:%M") if out_leg.departure_datetime else "",
                    "arrival_time": out_leg.arrival_datetime.strftime("%H:%M") if out_leg.arrival_datetime else "",
                    "return_departure_time": return_flight.legs[0].departure_datetime.strftime("%H:%M") if return_flight.legs[0].departure_datetime else "",
                    "return_arrival_time": ret_leg.arrival_datetime.strftime("%H:%M") if ret_leg.arrival_datetime else "",
                    "duration": outbound.duration or 0,
                    "stops": outbound.stops,
                    "origin": str(out_leg.departure_airport.name),
                    "destination": str(out_leg.arrival_airport.name),
                    "layovers": _extract_layovers(outbound.legs),
                    "return_layovers": _extract_layovers(return_flight.legs),
                }
            else:
                # Multi-city or other tuple
                first = flight[0]
                if first.price is None and flight[-1].price is None:
                    return None
                out_leg = first.legs[0]
                result = {
                    "price": flight[-1].price,
                    "currency": first.currency or "USD",
                    "airline": str(out_leg.airline.name).lstrip("_"),
                    "airline_name": _airline_display_name(out_leg.airline),
                    "flight_number": out_leg.flight_number or "",
                    "departure_time": out_leg.departure_datetime.strftime("%H:%M") if out_leg.departure_datetime else "",
                    "arrival_time": out_leg.arrival_datetime.strftime("%H:%M") if out_leg.arrival_datetime else "",
                    "duration": first.duration or 0,
                    "stops": first.stops,
                    "origin": str(out_leg.departure_airport.name),
                    "destination": str(out_leg.arrival_airport.name),
                    "layovers": _extract_layovers(first.legs),
                }
        else:
            # One-way
            if flight.price is None:
                return None
            leg = flight.legs[0]
            result = {
                "price": flight.price,
                "currency": flight.currency or "USD",
                "airline": str(leg.airline.name).lstrip("_"),
                "airline_name": _airline_display_name(leg.airline),
                "flight_number": leg.flight_number or "",
                "departure_time": leg.departure_datetime.strftime("%H:%M") if leg.departure_datetime else "",
                "arrival_time": leg.arrival_datetime.strftime("%H:%M") if leg.arrival_datetime else "",
                "duration": flight.duration or 0,
                "stops": flight.stops,
                "origin": str(leg.departure_airport.name),
                "destination": str(leg.arrival_airport.name),
                "layovers": _extract_layovers(flight.legs),
            }

        # Enrich with refund eligibility
        if result:
            refund = get_refund_eligibility_by_code(result["airline"])
            result["refund_badge"] = refund["badge"]
            result["refund_badge_label"] = refund["badge_label"]
            result["refund_type"] = refund["refund_type"]
            result["refund_eligible"] = refund["eligible"]
            result["manage_url"] = refund.get("manage_url", "")

        return result
    except Exception as e:
        logger.warning(f"Serialization error: {e}")
        return None


def _airline_display_name(airline_enum) -> str:
    """Convert airline enum to human-readable name."""
    name = str(airline_enum.name).lstrip("_")
    # Common mappings
    known = {
        "AA": "American Airlines", "DL": "Delta Air Lines", "UA": "United Airlines",
        "WN": "Southwest Airlines", "B6": "JetBlue", "NK": "Spirit Airlines",
        "F9": "Frontier Airlines", "AS": "Alaska Airlines", "MX": "Breeze Airways",
        "G4": "Allegiant Air", "SY": "Sun Country", "HA": "Hawaiian Airlines",
    }
    return known.get(name, name)


def _resolve_airport_safe(code: str):
    """Safely resolve airport code, returning None on failure."""
    try:
        from fli.core import resolve_airport
        return resolve_airport(code.strip().upper())
    except Exception:
        return None


# ── Date/Calendar Search ────────────────────────────────────────────────────


def _search_dates_sync(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    trip_duration: int = 5,
    is_round_trip: bool = True,
    max_stops: str = "ANY",
) -> list[dict]:
    """Search for cheapest dates in a range using fli's SearchDates API."""
    try:
        origin_airport = _resolve_airport_safe(origin)
        dest_airport = _resolve_airport_safe(destination)
        if not origin_airport or not dest_airport:
            return []

        stops = parse_max_stops(max_stops)
        segments, trip_type = build_date_search_segments(
            origin=origin_airport,
            destination=dest_airport,
            start_date=start_date,
            trip_duration=trip_duration,
            is_round_trip=is_round_trip,
        )

        filters = DateSearchFilters(
            trip_type=trip_type,
            passenger_info=PassengerInfo(adults=1),
            flight_segments=segments,
            stops=stops,
            from_date=start_date,
            to_date=end_date,
            duration=trip_duration if is_round_trip else None,
        )

        searcher = _get_date_search()
        results = searcher.search(filters)

        if not results:
            return []

        date_prices = []
        for r in results:
            dp = {
                "price": r.price,
                "currency": r.currency or "USD",
            }
            if isinstance(r.date, tuple):
                dp["date"] = r.date[0].strftime("%Y-%m-%d")
                if len(r.date) > 1:
                    dp["return_date"] = r.date[1].strftime("%Y-%m-%d")
            else:
                dp["date"] = r.date.strftime("%Y-%m-%d")
            date_prices.append(dp)

        date_prices.sort(key=lambda x: x["price"])
        return date_prices

    except Exception as e:
        logger.warning(f"Date search {origin}→{destination}: {e}")
        return []


# ── Hotel Search ─────────────────────────────────────────────────────────────


def _search_hotels_sync(city: str, checkin: str, checkout: str) -> list[dict]:
    """Search hotels using the direct Google Hotels API (hot_core)."""
    try:
        search_fn = _get_hotels_core()
        results = search_fn(city, checkin, checkout)
        if not results:
            return []

        hotels = []
        for h in results:
            total_str = h.get("total_price", "N/A")
            total_f = 0.0
            if total_str and total_str != "N/A":
                try:
                    total_f = float(total_str.replace("$", "").replace(",", ""))
                except (ValueError, AttributeError):
                    pass

            hotel_url = f"https://www.google.com/travel/hotels?q=hotels+in+{urllib.parse.quote(city)}+checkin+{checkin}+checkout+{checkout}"
            hotels.append({
                "name": h.get("name", "Unknown"),
                "price_per_night": h.get("price_per_night", "N/A"),
                "total_price": total_str,
                "total_price_float": total_f,
                "rating": h.get("rating", "N/A"),
                "city": city,
                "url": hotel_url,
            })
        return hotels

    except Exception as e:
        logger.warning(f"Hotel search in {city}: {e}")
        return []


# ── Async Wrappers (for FastAPI) ─────────────────────────────────────────────


async def search_flights_async(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    max_stops: str = "ANY",
    cabin_class: str = "ECONOMY",
    airline_filter: str | None = None,
    options: FlightSearchOptions | None = None,
) -> list[dict]:
    """Async wrapper — runs sync flight search in thread pool."""
    opts = options or FlightSearchOptions(
        max_stops=max_stops,
        cabin_class=cabin_class,
        airline_filter=airline_filter,
    )
    if options is None:
        opts.max_stops = max_stops
        opts.cabin_class = cabin_class
        opts.airline_filter = airline_filter

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: _search_flights_sync(
            origin,
            destination,
            departure_date,
            return_date,
            opts.max_stops,
            opts.cabin_class,
            opts.airline_filter,
            opts,
        ),
    )


def _get_booking_options_sync(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    flight_numbers: list[str] | None = None,
    options: FlightSearchOptions | None = None,
) -> dict[str, Any]:
    """Fetch vendor booking options for a single itinerary."""
    from fli.mcp.server import FlightSearchParams, _execute_booking_options

    opts = options or FlightSearchOptions()
    exclude = _merged_exclude_airlines(opts)
    params = FlightSearchParams(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        cabin_class=opts.cabin_class,
        max_stops=opts.max_stops,
        exclude_airlines=exclude,
        airlines=opts.airlines,
        alliance=opts.alliance,
        exclude_alliance=opts.exclude_alliance,
        departure_window=opts.departure_window,
        min_layover=opts.min_layover,
        max_layover=opts.max_layover,
        sort_by=opts.sort_by,
        currency=opts.currency,
        language=opts.language,
        country=opts.country,
    )
    return _execute_booking_options(params, flight_numbers)


async def get_booking_options_async(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    flight_numbers: list[str] | None = None,
    options: FlightSearchOptions | None = None,
) -> dict[str, Any]:
    """Async wrapper for vendor fare lookup."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: _get_booking_options_sync(
            origin,
            destination,
            departure_date,
            return_date,
            flight_numbers,
            options,
        ),
    )


async def search_dates_async(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    trip_duration: int = 5,
    is_round_trip: bool = True,
    max_stops: str = "ANY",
) -> list[dict]:
    """Async wrapper — runs sync date search in thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        _search_dates_sync,
        origin, destination, start_date, end_date,
        trip_duration, is_round_trip, max_stops,
    )


async def search_hotels_async(city: str, checkin: str, checkout: str) -> list[dict]:
    """Async wrapper — runs sync hotel search in thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        _search_hotels_sync,
        city, checkin, checkout,
    )


# ── Streaming Search Generators ─────────────────────────────────────────────


async def stream_flight_search(
    origins: list[str],
    destinations: list[str],
    start_date: str,
    end_date: str,
    durations: list[int],
    max_stops: str = "ANY",
    cabin_class: str = "ECONOMY",
    airline_filter: str | None = None,
    trip_type: str = "round_trip",
    departure_days: list[int] | None = None,
    options: FlightSearchOptions | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream flight results as SSE events for multiple origin/dest/date combos.

    Yields dicts with 'event' and 'data' keys for SSE formatting.
    """
    # Generate all trip permutations
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    trips = []
    is_one_way = trip_type == "one_way"

    cabin_list = [c.strip().upper() for c in cabin_class.split(",") if c.strip()]
    if not cabin_list:
        cabin_list = ["ECONOMY"]

    base_opts = options or FlightSearchOptions(
        max_stops=max_stops,
        cabin_class=cabin_class,
        airline_filter=airline_filter,
    )
    if options is None:
        base_opts.max_stops = max_stops
        base_opts.airline_filter = airline_filter

    for orig in origins:
        for dest in destinations:
            for cabin in cabin_list:
                if is_one_way:
                    # One-way: search each date in range
                    curr = start_dt
                    while curr <= end_dt:
                        if departure_days is None or curr.weekday() in departure_days:
                            trips.append({
                                "origin": orig.strip().upper(),
                                "destination": dest.strip().upper(),
                                "depart": curr.strftime("%Y-%m-%d"),
                                "return": None,
                                "cabin": cabin,
                                "label": f"{orig}→{dest} ({curr.strftime('%b %d')}) [{cabin}]",
                            })
                        curr += timedelta(days=1)
                else:
                    # Round-trip: each date × each duration
                    for dur in durations:
                        curr = start_dt
                        while curr <= end_dt:
                            if departure_days is None or curr.weekday() in departure_days:
                                ret_dt = curr + timedelta(days=dur)
                                if ret_dt <= end_dt + timedelta(days=max(durations)):
                                    trips.append({
                                        "origin": orig.strip().upper(),
                                        "destination": dest.strip().upper(),
                                        "depart": curr.strftime("%Y-%m-%d"),
                                        "return": ret_dt.strftime("%Y-%m-%d"),
                                        "cabin": cabin,
                                        "label": f"{orig}→{dest} ({curr.strftime('%b %d')}, {dur}d) [{cabin}]",
                                    })
                            curr += timedelta(days=1)

    total = len(trips)
    yield {"event": "status", "data": {"message": f"Scanning {total} flight combinations...", "total": total}}

    # Process in batches — fli client rate-limits (~10 req/s); 8 parallel stays safe
    BATCH_SIZE = 8
    completed = 0
    for i in range(0, len(trips), BATCH_SIZE):
        batch = trips[i:i + BATCH_SIZE]
        
        async def fetch_trip(trip):
            try:
                trip_opts = FlightSearchOptions(
                    max_stops=base_opts.max_stops,
                    cabin_class=trip["cabin"],
                    airline_filter=base_opts.airline_filter,
                    exclude_airlines=base_opts.exclude_airlines,
                    apply_default_exclusions=base_opts.apply_default_exclusions,
                    airlines=base_opts.airlines,
                    alliance=base_opts.alliance,
                    exclude_alliance=base_opts.exclude_alliance,
                    departure_window=base_opts.departure_window,
                    min_layover=base_opts.min_layover,
                    max_layover=base_opts.max_layover,
                    sort_by=base_opts.sort_by,
                    currency=base_opts.currency,
                    language=base_opts.language,
                    country=base_opts.country,
                )
                results = await search_flights_async(
                    origin=trip["origin"],
                    destination=trip["destination"],
                    departure_date=trip["depart"],
                    return_date=trip["return"],
                    options=trip_opts,
                )
                for r in results:
                    r["cabin_class"] = trip["cabin"]
                return trip, results
            except Exception as e:
                logger.warning(f"Error searching {trip['label']}: {e}")
                return trip, []

        batch_results = await asyncio.gather(*(fetch_trip(t) for t in batch))
        
        for trip, results in batch_results:
            completed += 1
            if results:
                best = results[0]
                flight_url = best.get("booking_url") or best.get("url") or _build_google_flights_url(
                    trip["origin"], trip["destination"],
                    trip["depart"], trip.get("return"),
                )
                yield {
                    "event": "flight_found",
                    "data": {
                        "label": trip["label"],
                        "origin": trip["origin"],
                        "destination": trip["destination"],
                        "depart_date": trip["depart"],
                        "return_date": trip.get("return"),
                        "price": best["price"],
                        "currency": best.get("currency", "USD"),
                        "airline": best.get("airline_name", best.get("airline", "")),
                        "flight_number": best.get("flight_number", ""),
                        "departure_time": best.get("departure_time", ""),
                        "arrival_time": best.get("arrival_time", ""),
                        "stops": best.get("stops", 0),
                        "url": flight_url,
                        "booking_url": flight_url,
                        "all_results": results,
                    },
                }

            yield {
                "event": "progress",
                "data": {"current": completed, "total": total, "trip": trip["label"]},
            }

        # Yield so SSE can flush; tiny pause helps avoid burst 429s from upstream
        await asyncio.sleep(0.02)

    yield {"event": "complete", "data": {"message": "Search complete", "total": total}}


async def stream_combined_search(
    origins: list[str],
    destinations: list[str],
    start_date: str,
    end_date: str,
    durations: list[int],
    max_stops: str = "ANY",
    hotel_city_override: str | None = None,
    options: FlightSearchOptions | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream combined flight + hotel results."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    trips = []
    for orig in origins:
        for dest in destinations:
            for dur in durations:
                curr = start_dt
                while curr <= end_dt:
                    ret_dt = curr + timedelta(days=dur)
                    if ret_dt <= end_dt + timedelta(days=max(durations)):
                        trips.append({
                            "origin": orig.strip().upper(),
                            "destination": dest.strip().upper(),
                            "depart": curr.strftime("%Y-%m-%d"),
                            "return": ret_dt.strftime("%Y-%m-%d"),
                            "label": f"{orig}→{dest} ({curr.strftime('%b %d')}, {dur}d)",
                        })
                    curr += timedelta(days=1)

    total = len(trips)
    yield {"event": "status", "data": {"message": f"Analyzing {total} trip combinations...", "total": total}}

    all_results = []
    search_opts = options or FlightSearchOptions(max_stops=max_stops)

    for i, trip in enumerate(trips):
        try:
            flights = _search_flights_sync(
                origin=trip["origin"],
                destination=trip["destination"],
                departure_date=trip["depart"],
                return_date=trip["return"],
                options=search_opts,
            )

            if flights:
                best_flight = flights[0]

                dest_city = hotel_city_override or iata_to_city(trip["destination"])
                hotels = _search_hotels_sync(dest_city, trip["depart"], trip["return"])

                if hotels:
                    best_hotel = hotels[0]
                    h_total = best_hotel.get("total_price_float", 0)
                    total_cost = best_flight["price"] + h_total

                    flight_url = best_flight.get("booking_url") or best_flight.get("url") or _build_google_flights_url(
                        trip["origin"], trip["destination"],
                        trip["depart"], trip["return"],
                    )

                    result = {
                        "label": trip["label"],
                        "total_estimate": total_cost,
                        "depart_date": trip["depart"],
                        "return_date": trip["return"],
                        "flight": {
                            "price": best_flight["price"],
                            "airline": best_flight.get("airline_name", best_flight.get("airline", "")),
                            "departure_time": best_flight.get("departure_time", ""),
                            "stops": best_flight.get("stops", 0),
                            "url": flight_url,
                            "booking_url": flight_url,
                        },
                        "hotel": {
                            "name": best_hotel["name"],
                            "rating": best_hotel["rating"],
                            "total_price": best_hotel["total_price"],
                            "total_float": h_total,
                            "city": dest_city,
                            "url": best_hotel["url"],
                        },
                    }
                    all_results.append(result)

        except Exception as e:
            logger.warning(f"Combined search error for {trip['label']}: {e}")

        yield {
            "event": "progress",
            "data": {"current": i + 1, "total": total, "trip": trip["label"]},
        }
        await asyncio.sleep(0)

    # Sort by total cost and send results
    all_results.sort(key=lambda x: x["total_estimate"])
    for result in all_results:
        yield {"event": "trip_found", "data": result}

    yield {"event": "complete", "data": {"message": "Analysis complete", "count": len(all_results)}}


def _build_google_flights_url(origin: str, dest: str, depart: str, ret: str | None = None) -> str:
    """Build a Google Flights deep link."""
    if ret:
        return f"https://www.google.com/travel/flights?q=Flights+from+{origin}+to+{dest}+on+{depart}+through+{ret}"
    else:
        return f"https://www.google.com/travel/flights?q=Flights+from+{origin}+to+{dest}+on+{depart}"
