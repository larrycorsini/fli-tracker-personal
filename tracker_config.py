"""Shared configuration for the Fli-Tracker daily search pipeline."""

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
FLIGHTS_JSON = "public/data/flights.json"

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

# Premium-cabin deal discovery (find_deals.py) — separate from economy region monitor.
PREMIUM_DEAL_ORIGINS = ["SLC", "PVU"]
PREMIUM_CABIN_CLASSES = ["BUSINESS", "PREMIUM_ECONOMY"]
PREMIUM_DATE_OFFSET_START = 14
PREMIUM_DATE_OFFSET_END = 45
PREMIUM_TRIP_DURATION = 7
PREMIUM_MAX_STOPS = "1"
PREMIUM_DEAL_OUTPUT_JSON = "premium_deals.json"
PREMIUM_DEALS_JSON = "public/data/premium-deals.json"

# Per-run destination cap keeps API volume ~50–80 calls (rotates daily).
PREMIUM_DESTINATIONS_PER_RUN = 12
PREMIUM_DESTINATIONS_PER_RUN_TEST = 3
PREMIUM_SHORTLIST_SIZE = 2
PREMIUM_SHORTLIST_SIZE_TEST = 1
PREMIUM_MAX_DEALS_PER_DEST = 3
PREMIUM_GLOBAL_TOP_N = 25

# Global cash thresholds (USD round-trip); tune per cabin and market type.
PREMIUM_DEAL_MAX_PRICE = {
    "domestic": {
        "BUSINESS": 800,
        "PREMIUM_ECONOMY": 500,
    },
    "international": {
        "BUSINESS": 2000,
        "PREMIUM_ECONOMY": 1200,
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
