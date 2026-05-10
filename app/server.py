"""FastAPI async server for Travel Planner Pro.

Replaces the old BaseHTTPRequestHandler with proper async SSE support,
REST endpoints, static file serving, and price drop tracking.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.airport_data import search_airports, iata_to_city
from app.engine import (
    search_dates_async,
    search_flights_async,
    search_hotels_async,
    stream_combined_search,
    stream_flight_search,
)
from app.tracker import (
    TrackerDB,
    check_all_flights,
    check_flight_price,
    get_refund_eligibility,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# ── Shared tracker DB instance ───────────────────────────────────────────────
_tracker_db: TrackerDB | None = None


def _get_db() -> TrackerDB:
    global _tracker_db
    if _tracker_db is None:
        _tracker_db = TrackerDB()
    return _tracker_db


# ── Background price check task ──────────────────────────────────────────────
_bg_task: asyncio.Task | None = None
BG_CHECK_INTERVAL = 6 * 60 * 60  # 6 hours


async def _background_price_checker():
    """Periodically check all tracked flights for price drops."""
    while True:
        try:
            await asyncio.sleep(BG_CHECK_INTERVAL)
            logger.info("Background price check starting...")
            db = _get_db()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, check_all_flights, db)
            logger.info(
                f"Background check complete: {result['checked']} checked, "
                f"{result['drops_found']} drops found, "
                f"${result['new_savings']:.0f} new savings"
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background price check error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle."""
    global _bg_task
    # Startup
    _get_db()  # Init DB on startup
    _bg_task = asyncio.create_task(_background_price_checker())
    logger.info("Price tracker initialized. Background checks every 6 hours.")
    yield
    # Shutdown
    if _bg_task:
        _bg_task.cancel()


app = FastAPI(title="Travel Planner Pro", version="2.1.0", lifespan=lifespan)

# ── Static files ─────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH ROUTES (unchanged from v2.0)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main SPA page."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/airports")
async def airport_search(q: str = Query("", min_length=0)):
    """Server-side airport autocomplete."""
    if len(q) < 2:
        return JSONResponse([])
    results = search_airports(q, limit=15)
    return JSONResponse(results)


@app.get("/api/search/insights")
async def get_search_insights(origin: str, destination: str):
    db = _get_db()
    insights = db.get_historical_percentiles(origin, destination)
    
    # If no history exists, we can't provide insights yet
    if not insights:
        return JSONResponse({"success": False, "message": "Not enough data yet"})
        
    return JSONResponse({"success": True, "insights": insights})

@app.get("/api/search/flights")
async def search_flights_sse(request: Request,
    origins: str = Query("PVU"),
    destinations: str = Query("DFW"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    durations: str = Query("5"),
    max_stops: str = Query("ANY"),
    cabin_class: str = Query("ECONOMY"),
    airline: str = Query(""),
    trip_type: str = Query("round_trip"),
):
    """Stream flight search results via SSE."""
    origin_list = [o.strip().upper() for o in origins.split(",") if o.strip()]
    dest_list = [d.strip().upper() for d in destinations.split(",") if d.strip()]

    try:
        dur_list = [int(d.strip()) for d in durations.split(",") if d.strip()]
    except ValueError:
        dur_list = [5]

    if not dur_list:
        dur_list = [5]

    async def event_generator():
        async for event in stream_flight_search(
            origins=origin_list,
            destinations=dest_list,
            start_date=start_date,
            end_date=end_date,
            durations=dur_list,
            max_stops=max_stops,
            cabin_class=cabin_class,
            airline_filter=airline if airline else None,
            trip_type=trip_type,
        ):
            if await request.is_disconnected():
                break
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"]),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/search/dates")
async def search_dates_endpoint(
    origin: str = Query("PVU"),
    destination: str = Query("DFW"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    durations: str = Query("5"),
    is_round_trip: bool = Query(True),
    max_stops: str = Query("ANY"),
):
    """Search for cheapest dates (non-streaming, returns JSON)."""
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    
    try:
        dur_list = [int(d.strip()) for d in durations.split(",") if d.strip()]
    except ValueError:
        dur_list = [5]
    if not dur_list:
        dur_list = [5]

    all_results = []
    
    if not is_round_trip:
        dur_list = [0] # Duration doesn't matter for one-way, just run once

    for dur in dur_list:
        results = await search_dates_async(
            origin=origin,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            trip_duration=dur if is_round_trip else 5,
            is_round_trip=is_round_trip,
            max_stops=max_stops,
        )
        all_results.extend(results)

    # Deduplicate in case of overlaps or identical results
    unique_map = {}
    for r in all_results:
        key = f"{r.get('date')}_{r.get('return_date', '')}"
        if key not in unique_map or r["price"] < unique_map[key]["price"]:
            unique_map[key] = r

    final_results = list(unique_map.values())
    final_results.sort(key=lambda x: (x["date"], x.get("return_date", "")))

    return JSONResponse({"success": True, "dates": final_results, "count": len(final_results)})


@app.get("/api/search/hotels")
async def search_hotels_endpoint(
    city: str = Query(""),
    checkin: str = Query(""),
    checkout: str = Query(""),
):
    """Search hotels by city and dates."""
    if not city or not checkin or not checkout:
        return JSONResponse({"success": False, "error": "city, checkin, checkout required"}, status_code=400)

    results = await search_hotels_async(city, checkin, checkout)
    return JSONResponse({"success": True, "hotels": results, "count": len(results)})


@app.get("/api/search/combined")
async def search_combined_sse(request: Request,
    origins: str = Query("PVU"),
    destinations: str = Query("DFW"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    durations: str = Query("5"),
    max_stops: str = Query("ANY"),
    hotel_city: str = Query(""),
):
    """Stream combined flight + hotel search results via SSE."""
    origin_list = [o.strip().upper() for o in origins.split(",") if o.strip()]
    dest_list = [d.strip().upper() for d in destinations.split(",") if d.strip()]

    try:
        dur_list = [int(d.strip()) for d in durations.split(",") if d.strip()]
    except ValueError:
        dur_list = [5]

    async def event_generator():
        async for event in stream_combined_search(
            origins=origin_list,
            destinations=dest_list,
            start_date=start_date,
            end_date=end_date,
            durations=dur_list,
            max_stops=max_stops,
            hotel_city_override=hotel_city if hotel_city else None,
        ):
            if await request.is_disconnected():
                break
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"]),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/resolve-city")
async def resolve_city(iata: str = Query("")):
    """Resolve IATA code to city name for hotel search auto-fill."""
    if not iata:
        return JSONResponse({"city": ""})
    city = iata_to_city(iata.strip().upper())
    return JSONResponse({"city": city})


# ══════════════════════════════════════════════════════════════════════════════
# TRACKER ROUTES (NEW — price drop monitoring)
# ══════════════════════════════════════════════════════════════════════════════

class AddFlightRequest(BaseModel):
    """Request body for adding a tracked flight."""
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    airline: str
    booked_price: float
    fare_class: str = "main_cabin"
    cabin_class: str = "ECONOMY"
    confirmation_code: str = ""


@app.post("/api/tracker/add")
async def tracker_add(req: AddFlightRequest):
    """Add a flight to price drop tracking."""
    db = _get_db()
    flight = db.add_flight(
        origin=req.origin,
        destination=req.destination,
        departure_date=req.departure_date,
        return_date=req.return_date,
        airline=req.airline,
        booked_price=req.booked_price,
        fare_class=req.fare_class,
        cabin_class=req.cabin_class,
        confirmation_code=req.confirmation_code,
    )
    return JSONResponse({"success": True, "flight": flight})


@app.get("/api/tracker/list")
async def tracker_list():
    """List all tracked flights with current prices and savings."""
    db = _get_db()
    flights = db.get_all_flights()
    stats = db.get_summary_stats()
    return JSONResponse({"success": True, "flights": flights, "stats": stats})


@app.post("/api/tracker/check/{flight_id}")
async def tracker_check_one(flight_id: int):
    """Force re-check price for one tracked flight."""
    db = _get_db()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, check_flight_price, db, flight_id)
    if result:
        return JSONResponse({"success": True, "flight": result})
    return JSONResponse({"success": False, "error": "Check failed or flight not found"}, status_code=404)


@app.post("/api/tracker/check-all")
async def tracker_check_all():
    """Re-check prices for all actively tracked flights."""
    db = _get_db()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, check_all_flights, db)
    return JSONResponse({"success": True, **result})


@app.get("/api/tracker/history/{flight_id}")
async def tracker_history(flight_id: int):
    """Get price history for a tracked flight."""
    db = _get_db()
    history = db.get_price_history(flight_id)
    return JSONResponse({"success": True, "history": history})


@app.delete("/api/tracker/{flight_id}")
async def tracker_delete(flight_id: int):
    """Stop tracking a flight."""
    db = _get_db()
    deleted = db.delete_flight(flight_id)
    if deleted:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "Flight not found"}, status_code=404)


@app.get("/api/refund-eligibility")
async def refund_eligibility(
    airline: str = Query(""),
    fare: str = Query("main_cabin"),
):
    """Check refund eligibility for an airline + fare class combo."""
    if not airline:
        return JSONResponse({"success": False, "error": "airline required"}, status_code=400)
    result = get_refund_eligibility(airline, fare)
    return JSONResponse({"success": True, **result})
    
@app.get("/api/trends")
async def get_trends(origin: str = Query(""), destination: str = Query("")):
    """Get historical price trends for a route."""
    if not origin or not destination:
        return JSONResponse({"success": False, "error": "origin and destination required"}, status_code=400)
    db = _get_db()
    percentiles = db.get_historical_percentiles(origin, destination)
    if percentiles:
        return JSONResponse({"success": True, "percentiles": percentiles})
    return JSONResponse({"success": False, "error": "No historical data available"})

# ══════════════════════════════════════════════════════════════════════════════
# TRIP PLANNER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

class TripCreateRequest(BaseModel):
    name: str

class TripItemRequest(BaseModel):
    item_type: str
    item_data: dict

@app.get("/api/trips")
async def get_trips():
    db = _get_db()
    trips = db.get_trips()
    return JSONResponse({"success": True, "trips": trips})

@app.post("/api/trips")
async def create_trip(req: TripCreateRequest):
    db = _get_db()
    trip_id = db.create_trip(req.name)
    return JSONResponse({"success": True, "trip_id": trip_id})

@app.delete("/api/trips/{trip_id}")
async def delete_trip(trip_id: int):
    db = _get_db()
    db.delete_trip(trip_id)
    return JSONResponse({"success": True})

@app.post("/api/trips/{trip_id}/items")
async def add_trip_item(trip_id: int, req: TripItemRequest):
    db = _get_db()
    item_id = db.add_trip_item(trip_id, req.item_type, req.item_data)
    return JSONResponse({"success": True, "item_id": item_id})

@app.delete("/api/trips/items/{item_id}")
async def delete_trip_item(item_id: int):
    db = _get_db()
    db.delete_trip_item(item_id)
    return JSONResponse({"success": True})

class TripItemOrderRequest(BaseModel):
    items: list[dict] # list of {"id": int, "order_index": int}

@app.put("/api/trips/{trip_id}/items/order")
async def update_trip_items_order(trip_id: int, req: TripItemOrderRequest):
    db = _get_db()
    db.update_trip_items_order(req.items)
    return JSONResponse({"success": True})

# ══════════════════════════════════════════════════════════════════════════════
# CURRENCY ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# Static fallback rates (relative to USD) to keep it dependency-free and fast.
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CAD": 1.36,
    "AUD": 1.53,
    "JPY": 150.0,
    "INR": 83.0
}

@app.get("/api/rates")
async def get_rates():
    return JSONResponse({"success": True, "rates": EXCHANGE_RATES})


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    """Entry point for the `fli-tracker` CLI command."""
    import webbrowser
    print("🛫 Travel Planner Pro: http://localhost:8000")
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
