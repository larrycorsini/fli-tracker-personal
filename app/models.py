"""Request and response models for Travel Planner Pro."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Search Mode ──────────────────────────────────────────────────────────────

class SearchMode(str, Enum):
    """What the user is searching for."""
    FLIGHTS = "flights"
    HOTELS = "hotels"
    COMBINED = "combined"
    FLEXIBLE_DATES = "flexible_dates"


class TripDirection(str, Enum):
    """Trip direction type."""
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


# ── Search Request ───────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Unified search request covering all modes."""
    mode: SearchMode = SearchMode.FLIGHTS
    trip_type: TripDirection = TripDirection.ROUND_TRIP

    # Airports
    origins: str = Field(default="PVU", description="Comma-separated origin IATA codes")
    destinations: str = Field(default="", description="Comma-separated destination IATA codes")

    # Dates — fixed mode
    departure_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    return_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")

    # Dates — flexible mode
    date_range_start: Optional[str] = Field(default=None, description="Start of flexible window")
    date_range_end: Optional[str] = Field(default=None, description="End of flexible window")
    trip_durations: Optional[str] = Field(default=None, description="Comma-separated days, e.g. '3,5,7'")

    # Filters
    max_stops: str = Field(default="ANY", description="NON_STOP, ONE_STOP, ANY")
    airline_filter: Optional[str] = Field(default=None, description="Airline name to filter")
    cabin_class: str = Field(default="ECONOMY", description="ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST")

    # Hotels
    hotel_city: Optional[str] = Field(default=None, description="Override city for hotel search")


# ── Response Models ──────────────────────────────────────────────────────────

class FlightResultItem(BaseModel):
    """A single flight result."""
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    price: float
    currency: str = "USD"
    airline: str = ""
    flight_number: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration: int = 0
    stops: int = 0
    url: str = ""


class HotelResultItem(BaseModel):
    """A single hotel result."""
    name: str
    price_per_night: str
    total_price: str
    rating: str = "N/A"
    city: str = ""
    url: str = ""


class CombinedResultItem(BaseModel):
    """A combined flight + hotel itinerary."""
    dates_label: str
    total_estimate: float
    flight: FlightResultItem
    hotel: HotelResultItem


class DatePriceItem(BaseModel):
    """A single date with its cheapest price."""
    date: str
    return_date: Optional[str] = None
    price: float
    currency: str = "USD"
