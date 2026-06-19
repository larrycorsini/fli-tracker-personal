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
