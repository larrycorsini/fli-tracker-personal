"""Shared configuration for the Fli-Tracker daily search pipeline."""

import os
from datetime import datetime

ORIGINS = ["SLC", "PVU"]

EXCLUDED_AIRLINES = ["F9", "MX", "NK", "G4", "SY", "XP"]

REGIONS = {
    "DFW": {
        "destinations": ["DFW"],
        "max_stops": "0",
        "type": "domestic",
        "alert_threshold": 300,
    },
    "California Coast": {
        "destinations": ["LAX", "SAN", "SNA"],
        "max_stops": "0",
        "type": "domestic",
        "alert_threshold": 250,
    },
    "Georgia": {
        "destinations": ["ATL", "SAV"],
        "max_stops": "1",
        "type": "domestic",
        "alert_threshold": 350,
    },
    "Cancun": {
        "destinations": ["CUN"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 500,
    },
    "El Salvador": {
        "destinations": ["SAL"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 550,
    },
    "Europe": {
        "destinations": ["LHR", "CDG", "FRA", "AMS"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 900,
    },
    "Greece": {
        "destinations": ["ATH", "SKG"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 900,
    },
    "Japan": {
        "destinations": ["HND", "NRT"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 1000,
    },
    "South Korea": {
        "destinations": ["ICN"],
        "max_stops": "1",
        "type": "international",
        "alert_threshold": 1000,
    },
}

OUTPUT_JSON = "best_direct.json"
SITE_URL = "https://flights.larrycorsini.com"
PLANNER_URL = os.environ.get("FLI_PLANNER_URL", "http://localhost:8000")
FLIGHTS_JSON = "public/data/flights.json"
PRIOR_PRICES_JSON = "public/data/prior_prices.json"

# Region-aware heatmap color tiers (USD round-trip).
HEATMAP_THRESHOLDS = {
    "domestic": {"low": 320, "mid": 500},
    "international": {"low": 700, "mid": 1100},
}

# Months (1–12) when a region is actively searched; omitted regions run year-round.
REGION_ACTIVE_MONTHS: dict[str, list[int]] = {
    "Cancun": [10, 11, 12, 1, 2, 3, 4],
    "Europe": [3, 4, 5, 6, 9, 10],
    "Greece": [4, 5, 6, 9, 10],
    "Japan": [3, 4, 5, 10, 11],
    "South Korea": [3, 4, 5, 9, 10, 11],
}

# Display caps — keep HTML/JSON payloads small for faster page loads.
MAX_FARE_GROUPS_PER_REGION = 15
MAX_TIMES_PER_GROUP = 3

# Two-phase search: SearchDates shortlist size per region, then SearchFlights on those pairs.
SHORTLIST_SIZE = 20
SHORTLIST_SIZE_TEST = 3
DOMESTIC_TRIP_DURATIONS = [3, 4]
INTERNATIONAL_TRIP_DURATIONS = [7, 10]


INTERNATIONAL_REGIONS = [
    name for name, cfg in REGIONS.items() if cfg.get("type") == "international"
]


def region_active(region_name: str, when: datetime | None = None) -> bool:
    """Return whether a region should be searched on the given date."""
    from datetime import datetime as dt

    when = when or dt.now()
    months = REGION_ACTIVE_MONTHS.get(region_name)
    if not months:
        return True
    return when.month in months


def heatmap_tier(price: float, region_name: str) -> str:
    """Return heatmap CSS class suffix: low, mid, or high."""
    region_type = REGIONS.get(region_name, {}).get("type", "domestic")
    thresholds = HEATMAP_THRESHOLDS.get(region_type, HEATMAP_THRESHOLDS["domestic"])
    if price < thresholds["low"]:
        return "low"
    if price <= thresholds["mid"]:
        return "mid"
    return "high"


def planner_track_url(origin: str, destination: str, depart: str, ret: str | None = None) -> str:
    """Deep link into Travel Planner Pro to pre-fill price tracking."""
    from urllib.parse import quote

    parts = [origin, destination, depart]
    if ret:
        parts.append(ret)
    query = quote(",".join(parts))
    return f"{PLANNER_URL.rstrip('/')}/?track={query}"

# Premium-cabin deal discovery (find_deals.py) — separate from economy region monitor.
PREMIUM_DEAL_ORIGINS = ["SLC", "PVU"]
PREMIUM_CABIN_CLASSES = ["BUSINESS", "PREMIUM_ECONOMY"]
# Wider departure window: day+7 through day+90 (test mode narrows in find_deals.py).
PREMIUM_DATE_OFFSET_START = 7
PREMIUM_DATE_OFFSET_END = 90
# Flexible trip lengths; two durations rotate daily to cap API volume (see durations_for_run).
PREMIUM_TRIP_DURATIONS = [3, 4, 5, 7, 10, 14]
PREMIUM_TRIP_DURATIONS_PER_RUN = 2
PREMIUM_TRIP_DURATIONS_PER_RUN_TEST = 1
PREMIUM_MAX_STOPS = "1"
PREMIUM_DEAL_OUTPUT_JSON = "premium_deals.json"
PREMIUM_DEALS_JSON = "public/data/premium-deals.json"

# Per-run caps keep API volume ~72–96 calls/day (destinations + durations rotate daily).
PREMIUM_DESTINATIONS_PER_RUN = 10
PREMIUM_DESTINATIONS_PER_RUN_TEST = 3
PREMIUM_SHORTLIST_SIZE = 2
PREMIUM_SHORTLIST_SIZE_TEST = 1
PREMIUM_MAX_DEALS_PER_DEST = 3
PREMIUM_GLOBAL_TOP_N = 30

# Chase Sapphire Preferred portal redemption (¢/point) for estimated points on cash fares.
CHASE_POINTS_CENT_VALUE = 1.25

# Global cash thresholds (USD round-trip); tune per cabin and market type.
PREMIUM_DEAL_MAX_PRICE = {
    "domestic": {
        "BUSINESS": 1400,
        "PREMIUM_ECONOMY": 800,
    },
    "international": {
        "BUSINESS": 3800,
        "PREMIUM_ECONOMY": 2000,
    },
}

# seats.aero Partner API (cached search only — Pro: 1000 calls/day, resets UTC midnight).
SEATS_AERO_DAILY_LIMIT = 1000
SEATS_AERO_DAILY_RESERVE = 50  # headroom for manual/ad-hoc queries
SEATS_AERO_MAX_CALLS_PER_RUN = 10  # matches PREMIUM_DESTINATIONS_PER_RUN rotation
SEATS_AERO_ENABLED = bool(os.environ.get("SEATS_AERO_API_KEY", "").strip())

# Award/miles thresholds (round-trip). Google Flights does not return award prices;
# find_deals.py applies these when seats.aero award data is available (SEATS_AERO_API_KEY).
PREMIUM_DEAL_MAX_POINTS = {
    "domestic": {
        "BUSINESS": 100_000,
        "PREMIUM_ECONOMY": 60_000,
    },
    "international": {
        "BUSINESS": 200_000,
        "PREMIUM_ECONOMY": 120_000,
    },
}

# Curated worldwide deal-hunt destinations (~50 airports).
PREMIUM_DEAL_DESTINATIONS: list[dict[str, str]] = [
    # US hubs & leisure
    {"airport": "JFK", "label": "New York", "region_label": "US East", "type": "domestic"},
    {"airport": "EWR", "label": "Newark", "region_label": "US East", "type": "domestic"},
    {"airport": "BOS", "label": "Boston", "region_label": "US East", "type": "domestic"},
    {"airport": "DCA", "label": "Washington DC", "region_label": "US East", "type": "domestic"},
    {"airport": "PHL", "label": "Philadelphia", "region_label": "US East", "type": "domestic"},
    {"airport": "ATL", "label": "Atlanta", "region_label": "US South", "type": "domestic"},
    {"airport": "MIA", "label": "Miami", "region_label": "US South", "type": "domestic"},
    {"airport": "FLL", "label": "Fort Lauderdale", "region_label": "US South", "type": "domestic"},
    {"airport": "CLT", "label": "Charlotte", "region_label": "US South", "type": "domestic"},
    {"airport": "ORD", "label": "Chicago", "region_label": "US Midwest", "type": "domestic"},
    {"airport": "MSP", "label": "Minneapolis", "region_label": "US Midwest", "type": "domestic"},
    {"airport": "DTW", "label": "Detroit", "region_label": "US Midwest", "type": "domestic"},
    {"airport": "DFW", "label": "Dallas", "region_label": "US South", "type": "domestic"},
    {"airport": "IAH", "label": "Houston", "region_label": "US South", "type": "domestic"},
    {"airport": "DEN", "label": "Denver", "region_label": "US West", "type": "domestic"},
    {"airport": "PHX", "label": "Phoenix", "region_label": "US West", "type": "domestic"},
    {"airport": "LAX", "label": "Los Angeles", "region_label": "US West", "type": "domestic"},
    {"airport": "SAN", "label": "San Diego", "region_label": "US West", "type": "domestic"},
    {"airport": "SFO", "label": "San Francisco", "region_label": "US West", "type": "domestic"},
    {"airport": "SEA", "label": "Seattle", "region_label": "US West", "type": "domestic"},
    {"airport": "PDX", "label": "Portland", "region_label": "US West", "type": "domestic"},
    {"airport": "AUS", "label": "Austin", "region_label": "US South", "type": "domestic"},
    {"airport": "BNA", "label": "Nashville", "region_label": "US South", "type": "domestic"},
    {"airport": "HNL", "label": "Honolulu", "region_label": "Hawaii", "type": "domestic"},
    # Europe
    {"airport": "LHR", "label": "London", "region_label": "Europe", "type": "international"},
    {"airport": "CDG", "label": "Paris", "region_label": "Europe", "type": "international"},
    {"airport": "AMS", "label": "Amsterdam", "region_label": "Europe", "type": "international"},
    {"airport": "FRA", "label": "Frankfurt", "region_label": "Europe", "type": "international"},
    {"airport": "MAD", "label": "Madrid", "region_label": "Europe", "type": "international"},
    {"airport": "BCN", "label": "Barcelona", "region_label": "Europe", "type": "international"},
    {"airport": "FCO", "label": "Rome", "region_label": "Europe", "type": "international"},
    {"airport": "ZRH", "label": "Zurich", "region_label": "Europe", "type": "international"},
    {"airport": "DUB", "label": "Dublin", "region_label": "Europe", "type": "international"},
    {"airport": "CPH", "label": "Copenhagen", "region_label": "Europe", "type": "international"},
    {"airport": "IST", "label": "Istanbul", "region_label": "Europe", "type": "international"},
    # Asia & Pacific
    {"airport": "HND", "label": "Tokyo Haneda", "region_label": "Japan", "type": "international"},
    {"airport": "NRT", "label": "Tokyo Narita", "region_label": "Japan", "type": "international"},
    {"airport": "ICN", "label": "Seoul", "region_label": "South Korea", "type": "international"},
    {"airport": "SIN", "label": "Singapore", "region_label": "Asia", "type": "international"},
    {"airport": "HKG", "label": "Hong Kong", "region_label": "Asia", "type": "international"},
    {"airport": "BKK", "label": "Bangkok", "region_label": "Asia", "type": "international"},
    {"airport": "TPE", "label": "Taipei", "region_label": "Asia", "type": "international"},
    {"airport": "SYD", "label": "Sydney", "region_label": "Oceania", "type": "international"},
    {"airport": "AKL", "label": "Auckland", "region_label": "Oceania", "type": "international"},
    # Latin America & Caribbean
    {
        "airport": "CUN",
        "label": "Cancun",
        "region_label": "Mexico & Caribbean",
        "type": "international",
    },
    {
        "airport": "MEX",
        "label": "Mexico City",
        "region_label": "Mexico & Caribbean",
        "type": "international",
    },
    {
        "airport": "SJO",
        "label": "San Jose CR",
        "region_label": "Central America",
        "type": "international",
    },
    {"airport": "BOG", "label": "Bogota", "region_label": "South America", "type": "international"},
    {
        "airport": "GRU",
        "label": "Sao Paulo",
        "region_label": "South America",
        "type": "international",
    },
    {
        "airport": "EZE",
        "label": "Buenos Aires",
        "region_label": "South America",
        "type": "international",
    },
    {"airport": "LIM", "label": "Lima", "region_label": "South America", "type": "international"},
    # Middle East
    {"airport": "DXB", "label": "Dubai", "region_label": "Middle East", "type": "international"},
    {"airport": "DOH", "label": "Doha", "region_label": "Middle East", "type": "international"},
]
