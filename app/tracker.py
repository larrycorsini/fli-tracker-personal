"""Price drop tracker — SQLite-backed flight monitoring + airline refund policies.

Monitors booked flights for price drops using fli's search engine.
Stores price history and determines refund eligibility per airline.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tracker")

DB_PATH = Path(__file__).parent / "data" / "tracker.db"

# ── Airline Refund Policy Database ───────────────────────────────────────────

AIRLINE_POLICIES = {
    # Major US carriers with free change policies (Main Cabin+)
    "American Airlines": {
        "code": "AA",
        "eligible": True,
        "refund_type": "Trip Credit",
        "method": "Cancel existing booking → receive Trip Credit → rebook at lower fare",
        "credit_expiry": "1 year from issuance",
        "excluded_fares": ["Basic Economy"],
        "manage_url": "https://www.aa.com/reservation/view/find-your-reservation",
        "notes": "Main Cabin and above. Change/cancel free. Fare difference as Trip Credit.",
    },
    "Delta Air Lines": {
        "code": "DL",
        "eligible": True,
        "refund_type": "eCredit",
        "method": "Cancel → receive eCredit → rebook same flight at lower fare",
        "credit_expiry": "1 year from original purchase",
        "excluded_fares": ["Basic Economy"],
        "manage_url": "https://www.delta.com/mytrips/",
        "notes": "Main Cabin and above. Cancel for eCredit, rebook at lower price.",
    },
    "United Airlines": {
        "code": "UA",
        "eligible": True,
        "refund_type": "Future Flight Credit",
        "method": "Cancel → Future Flight Credit for the difference → rebook",
        "credit_expiry": "1 year from original ticket issue date",
        "excluded_fares": ["Basic Economy"],
        "manage_url": "https://www.united.com/en/us/manageres/mytrips",
        "notes": "Economy and above (not Basic Economy). Free changes.",
    },
    "Southwest Airlines": {
        "code": "WN",
        "eligible": True,
        "refund_type": "Travel Credit",
        "method": "Change flight online to same flight at lower fare → instant credit",
        "credit_expiry": "Varies by fare type",
        "excluded_fares": [],
        "manage_url": "https://www.southwest.com/air/manage-reservation/",
        "notes": "Easiest airline for price drops. All fares eligible. Change online directly.",
    },
    "Alaska Airlines": {
        "code": "AS",
        "eligible": True,
        "refund_type": "Travel Credit",
        "method": "Cancel ticket → receive travel credit → rebook at lower fare",
        "credit_expiry": "1 year from issuance",
        "excluded_fares": ["Saver"],
        "manage_url": "https://www.alaskaair.com/booking/manage-trip",
        "notes": "Main and above (not Saver). Cancel for travel credit.",
    },
    "Hawaiian Airlines": {
        "code": "HA",
        "eligible": True,
        "refund_type": "Travel Credit",
        "method": "Cancel → travel credit → rebook at lower fare",
        "credit_expiry": "1 year from issuance",
        "excluded_fares": ["Basic Economy"],
        "manage_url": "https://www.hawaiianairlines.com/manage/my-trips",
        "notes": "Main Cabin and above.",
    },
    "JetBlue": {
        "code": "B6",
        "eligible": True,
        "refund_type": "Travel Credit",
        "method": "Cancel → JetBlue travel credit → rebook",
        "credit_expiry": "1 year from issuance",
        "excluded_fares": ["Blue Basic"],
        "manage_url": "https://www.jetblue.com/manage-trips",
        "notes": "Blue fare and above (not Blue Basic).",
    },
    # Budget carriers — NOT eligible for free changes
    "Spirit Airlines": {
        "code": "NK",
        "eligible": False,
        "refund_type": "N/A",
        "method": "Change fees apply — typically not worth it for small drops",
        "credit_expiry": "N/A",
        "excluded_fares": ["all"],
        "manage_url": "https://www.spirit.com/manage-trip",
        "notes": "Change fees apply to all fares. Not recommended for price drop tracking.",
    },
    "Frontier Airlines": {
        "code": "F9",
        "eligible": False,
        "refund_type": "N/A",
        "method": "Change fees apply",
        "credit_expiry": "N/A",
        "excluded_fares": ["all"],
        "manage_url": "https://www.flyfrontier.com/manage-travel/my-trips/",
        "notes": "Change fees apply. Not recommended for price drop tracking.",
    },
    "Allegiant Air": {
        "code": "G4",
        "eligible": False,
        "refund_type": "N/A",
        "method": "No free changes",
        "credit_expiry": "N/A",
        "excluded_fares": ["all"],
        "manage_url": "https://www.allegiantair.com/manage-travel",
        "notes": "No free change policy. Not eligible.",
    },
    "Breeze Airways": {
        "code": "MX",
        "eligible": True,
        "refund_type": "BreezeCredit",
        "method": "Cancel → BreezeCredit → rebook",
        "credit_expiry": "2 years",
        "excluded_fares": [],
        "manage_url": "https://www.flybreeze.com/manage",
        "notes": "Nice and Nicer fares eligible. Cancel for BreezeCredit.",
    },
    "Sun Country": {
        "code": "SY",
        "eligible": False,
        "refund_type": "N/A",
        "method": "Change fees may apply",
        "credit_expiry": "N/A",
        "excluded_fares": ["all"],
        "manage_url": "https://www.suncountry.com/manage-trip",
        "notes": "Limited change policy. Generally not recommended.",
    },
}

# Build reverse lookup by code
_CODE_TO_AIRLINE = {}
for name, policy in AIRLINE_POLICIES.items():
    _CODE_TO_AIRLINE[policy["code"]] = name


def get_refund_eligibility(airline_identifier: str, fare_class: str = "main_cabin") -> dict:
    """Get refund eligibility for an airline + fare class combo.

    Args:
        airline_identifier: Airline name or IATA code (e.g. "AA", "American Airlines")
        fare_class: Fare class (e.g. "main_cabin", "basic_economy", "economy")

    Returns:
        Dict with eligibility info, instructions, and manage booking URL.
    """
    # Resolve airline name
    airline_name = airline_identifier
    if len(airline_identifier) <= 3:
        airline_name = _CODE_TO_AIRLINE.get(airline_identifier.upper(), airline_identifier)

    policy = AIRLINE_POLICIES.get(airline_name)
    if not policy:
        # Try fuzzy match
        for name, p in AIRLINE_POLICIES.items():
            if airline_identifier.lower() in name.lower() or airline_identifier.upper() == p["code"]:
                policy = p
                airline_name = name
                break

    if not policy:
        return {
            "airline": airline_identifier,
            "eligible": False,
            "badge": "unknown",
            "badge_label": "Unknown Policy",
            "refund_type": "N/A",
            "method": "Unable to determine refund policy for this airline.",
            "manage_url": "",
            "notes": "",
            "dot_24h": True,
        }

    # Check if fare class is excluded
    fare_lower = fare_class.lower().replace("_", " ")
    is_excluded = False
    for excl in policy.get("excluded_fares", []):
        if excl.lower() in fare_lower or fare_lower in excl.lower():
            is_excluded = True
            break
    if "all" in [e.lower() for e in policy.get("excluded_fares", [])]:
        is_excluded = True

    eligible = policy["eligible"] and not is_excluded

    if eligible:
        badge = "eligible"
        badge_label = f"{policy['refund_type']} Eligible"
    elif policy["eligible"] and is_excluded:
        badge = "24h_only"
        badge_label = "24h Refund Only"
    else:
        badge = "ineligible"
        badge_label = "No Free Changes"

    return {
        "airline": airline_name,
        "airline_code": policy["code"],
        "eligible": eligible,
        "badge": badge,
        "badge_label": badge_label,
        "refund_type": policy["refund_type"],
        "method": policy["method"],
        "credit_expiry": policy.get("credit_expiry", "N/A"),
        "manage_url": policy["manage_url"],
        "notes": policy["notes"],
        "excluded_fares": policy.get("excluded_fares", []),
        "dot_24h": True,  # DOT 24-hour rule always applies
    }


def get_refund_eligibility_by_code(airline_code: str) -> dict:
    """Quick lookup for flight card badge — just needs the IATA code."""
    return get_refund_eligibility(airline_code, "main_cabin")


# ── SQLite Database ──────────────────────────────────────────────────────────

class TrackerDB:
    """Lightweight SQLite database for tracking booked flights and price history."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the tracker database."""
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row_factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tracked_flights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    airline TEXT NOT NULL DEFAULT '',
                    airline_code TEXT NOT NULL DEFAULT '',
                    cabin_class TEXT NOT NULL DEFAULT 'ECONOMY',
                    fare_class TEXT NOT NULL DEFAULT 'main_cabin',
                    booked_price REAL NOT NULL,
                    current_price REAL,
                    lowest_price REAL,
                    total_savings REAL NOT NULL DEFAULT 0.0,
                    refund_eligible INTEGER NOT NULL DEFAULT 0,
                    refund_type TEXT NOT NULL DEFAULT 'N/A',
                    status TEXT NOT NULL DEFAULT 'tracking',
                    confirmation_code TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_checked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id INTEGER NOT NULL,
                    checked_at TEXT NOT NULL,
                    price REAL NOT NULL,
                    price_delta REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (flight_id) REFERENCES tracked_flights(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    price REAL NOT NULL,
                    airline TEXT,
                    searched_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trip_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    item_type TEXT NOT NULL, -- 'flight' or 'hotel'
                    item_data TEXT NOT NULL, -- JSON
                    added_at TEXT NOT NULL,
                    order_index INTEGER DEFAULT 0,
                    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
                );
            """)
            
            # Migration: add order_index if it doesn't exist
            try:
                conn.execute("ALTER TABLE trip_items ADD COLUMN order_index INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass # Column already exists
                
            conn.commit()
        finally:
            conn.close()

    def add_flight(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        airline: str,
        booked_price: float,
        fare_class: str = "main_cabin",
        cabin_class: str = "ECONOMY",
        confirmation_code: str = "",
    ) -> dict:
        """Add a flight to track. Returns the created flight record."""
        eligibility = get_refund_eligibility(airline, fare_class)
        airline_code = eligibility.get("airline_code", "")
        now = datetime.now().isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO tracked_flights
                   (origin, destination, departure_date, return_date, airline, airline_code,
                    cabin_class, fare_class, booked_price, current_price, lowest_price,
                    refund_eligible, refund_type, confirmation_code, created_at, last_checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    origin.upper(), destination.upper(), departure_date, return_date,
                    eligibility.get("airline", airline), airline_code,
                    cabin_class, fare_class, booked_price, booked_price, booked_price,
                    1 if eligibility["eligible"] else 0,
                    eligibility.get("refund_type", "N/A"),
                    confirmation_code, now, None,
                ),
            )
            conn.commit()
            flight_id = cursor.lastrowid

            # Log initial price
            conn.execute(
                "INSERT INTO price_history (flight_id, checked_at, price, price_delta) VALUES (?, ?, ?, ?)",
                (flight_id, now, booked_price, 0.0),
            )
            conn.commit()

            return self._get_flight_by_id(conn, flight_id)
        finally:
            conn.close()

    def get_all_flights(self) -> list[dict]:
        """Get all tracked flights with enriched eligibility info and price history."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM tracked_flights ORDER BY created_at DESC"
            ).fetchall()
            flights = [self._enrich_flight(dict(r)) for r in rows]
            # Attach price history to each flight
            for f in flights:
                ph_rows = conn.execute(
                    "SELECT price, checked_at FROM price_history WHERE flight_id = ? ORDER BY checked_at ASC",
                    (f["id"],),
                ).fetchall()
                f["price_history"] = [dict(r) for r in ph_rows]
            return flights
        finally:
            conn.close()

    def get_flight(self, flight_id: int) -> Optional[dict]:
        """Get a single tracked flight."""
        conn = self._get_conn()
        try:
            return self._get_flight_by_id(conn, flight_id)
        finally:
            conn.close()

    def update_price(self, flight_id: int, new_price: float) -> dict:
        """Record a new price check for a tracked flight."""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            flight = self._get_flight_by_id(conn, flight_id)
            if not flight:
                return {"error": "Flight not found"}

            booked = flight["booked_price"]
            delta = booked - new_price  # positive = savings
            current_lowest = flight["lowest_price"] or booked
            new_lowest = min(current_lowest, new_price)
            total_savings = max(0, booked - new_lowest)

            conn.execute(
                """UPDATE tracked_flights
                   SET current_price = ?, lowest_price = ?, total_savings = ?, last_checked_at = ?
                   WHERE id = ?""",
                (new_price, new_lowest, total_savings, now, flight_id),
            )
            conn.execute(
                "INSERT INTO price_history (flight_id, checked_at, price, price_delta) VALUES (?, ?, ?, ?)",
                (flight_id, now, new_price, delta),
            )
            conn.commit()
            return self._get_flight_by_id(conn, flight_id)
        finally:
            conn.close()

    def get_price_history(self, flight_id: int) -> list[dict]:
        """Get price history for a tracked flight."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM price_history WHERE flight_id = ? ORDER BY checked_at ASC",
                (flight_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_flight(self, flight_id: int) -> bool:
        """Delete a tracked flight and its history."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM price_history WHERE flight_id = ?", (flight_id,))
            result = conn.execute("DELETE FROM tracked_flights WHERE id = ?", (flight_id,))
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def expire_departed_flights(self):
        """Mark flights as 'departed' if departure_date has passed."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE tracked_flights SET status = 'departed' WHERE departure_date < ? AND status = 'tracking'",
                (today,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_active_flights(self) -> list[dict]:
        """Get only flights that are still being tracked (not departed)."""
        self.expire_departed_flights()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM tracked_flights WHERE status = 'tracking' ORDER BY departure_date ASC"
            ).fetchall()
            return [self._enrich_flight(dict(r)) for r in rows]
        finally:
            conn.close()

    def get_summary_stats(self) -> dict:
        """Get summary stats for the tracker dashboard."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT
                     COUNT(*) as total_count,
                     COUNT(CASE WHEN status = 'tracking' THEN 1 END) as active_count,
                     COALESCE(SUM(total_savings), 0) as total_savings,
                     COALESCE(SUM(CASE WHEN total_savings > 0 THEN 1 ELSE 0 END), 0) as price_drops
                   FROM tracked_flights"""
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def _get_flight_by_id(self, conn: sqlite3.Connection, flight_id: int) -> Optional[dict]:
        """Internal: get flight by ID."""
        row = conn.execute(
            "SELECT * FROM tracked_flights WHERE id = ?", (flight_id,)
        ).fetchone()
        if not row:
            return None
        return self._enrich_flight(dict(row))

    def _enrich_flight(self, flight: dict) -> dict:
        """Add computed fields to a flight record."""
        booked = flight.get("booked_price", 0)
        current = flight.get("current_price", booked)
        flight["price_delta"] = booked - current
        flight["price_delta_pct"] = round((flight["price_delta"] / booked * 100), 1) if booked else 0
        flight["has_savings"] = flight["price_delta"] > 0
        flight["savings"] = flight.get("total_savings", 0)
        flight["last_checked"] = flight.get("last_checked_at")

        # Add eligibility info
        eligibility = get_refund_eligibility(
            flight.get("airline", ""),
            flight.get("fare_class", "main_cabin"),
        )
        flight["eligibility"] = eligibility
        flight["refund_badge"] = eligibility.get("badge", "")
        flight["refund_badge_label"] = eligibility.get("badge_label", "")
        flight["manage_url"] = eligibility.get("manage_url", "")
        return flight

    def log_search(self, origin: str, destination: str, departure_date: str, return_date: Optional[str], price: float, airline: str):
        """Log a search result for historical price trends."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO search_history 
                   (origin, destination, departure_date, return_date, price, airline, searched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (origin.upper(), destination.upper(), departure_date, return_date, price, airline, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def get_historical_average(self, origin: str, destination: str) -> Optional[float]:
        """Get the historical average price for a route."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT AVG(price) as avg_price FROM search_history WHERE origin = ? AND destination = ?",
                (origin.upper(), destination.upper())
            ).fetchone()
            if row and row["avg_price"]:
                return round(row["avg_price"], 2)
            return None
        finally:
            conn.close()

    def get_historical_percentiles(self, origin: str, destination: str) -> Optional[dict]:
        """Get 15th and 85th percentiles to determine if a price is Great/Typical/High."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT price FROM search_history WHERE origin = ? AND destination = ? ORDER BY price ASC",
                (origin.upper(), destination.upper())
            ).fetchall()
            if not rows or len(rows) < 3:
                return None
            
            prices = [r["price"] for r in rows]
            p15_idx = max(0, int(len(prices) * 0.15))
            p85_idx = min(len(prices) - 1, int(len(prices) * 0.85))
            
            return {
                "great": prices[p15_idx],
                "high": prices[p85_idx],
                "avg": sum(prices) / len(prices)
            }
        finally:
            conn.close()

    # ── TRIP PLANNER METHODS ────────────────────────────────────────────────
    
    def get_trips(self) -> list[dict]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, created_at FROM trips ORDER BY created_at DESC")
            trips = [{"id": row[0], "name": row[1], "created_at": row[2]} for row in cursor.fetchall()]
            for trip in trips:
                cursor.execute("SELECT id, item_type, item_data, order_index FROM trip_items WHERE trip_id = ? ORDER BY order_index ASC, id ASC", (trip["id"],))
                items = []
                for i_row in cursor.fetchall():
                    try:
                        data = json.loads(i_row[2])
                    except:
                        data = {}
                    items.append({"id": i_row[0], "type": i_row[1], "data": data, "order_index": i_row[3]})
                trip["items"] = items
            return trips
        finally:
            conn.close()

    def create_trip(self, name: str) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO trips (name, created_at) VALUES (?, ?)",
                (name, datetime.now().isoformat())
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def delete_trip(self, trip_id: int):
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            conn.commit()
        finally:
            conn.close()

    def add_trip_item(self, trip_id: int, item_type: str, item_data: dict) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            # Get max order_index
            cursor.execute("SELECT MAX(order_index) FROM trip_items WHERE trip_id = ?", (trip_id,))
            max_idx = cursor.fetchone()[0]
            next_idx = 0 if max_idx is None else max_idx + 1

            cursor.execute(
                "INSERT INTO trip_items (trip_id, item_type, item_data, added_at, order_index) VALUES (?, ?, ?, ?, ?)",
                (trip_id, item_type, json.dumps(item_data), datetime.now().isoformat(), next_idx)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_trip_items_order(self, item_orders: list[dict]) -> None:
        """item_orders is a list of {"id": int, "order_index": int}"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            for item in item_orders:
                cursor.execute(
                    "UPDATE trip_items SET order_index = ? WHERE id = ?",
                    (item["order_index"], item["id"])
                )
            conn.commit()
        finally:
            conn.close()

    def delete_trip_item(self, item_id: int):
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM trip_items WHERE id = ?", (item_id,))
            conn.commit()
        finally:
            conn.close()



# ── Price Check Engine Integration ───────────────────────────────────────────

def check_flight_price(db: TrackerDB, flight_id: int) -> Optional[dict]:
    """Check current price of a tracked flight using fli's search engine.

    Returns the updated flight record, or None if check failed.
    """
    flight = db.get_flight(flight_id)
    if not flight or flight["status"] != "tracking":
        return None

    try:
        from app.engine import _search_flights_sync

        results = _search_flights_sync(
            origin=flight["origin"],
            destination=flight["destination"],
            departure_date=flight["departure_date"],
            return_date=flight.get("return_date"),
            max_stops="ANY",
            cabin_class=flight.get("cabin_class", "ECONOMY"),
        )

        if results:
            cheapest = results[0]["price"]
            updated = db.update_price(flight_id, cheapest)
            
            # Send macOS notification if price dropped
            if updated:
                old_savings = flight.get("total_savings", 0)
                new_savings = updated.get("total_savings", 0)
                if new_savings > old_savings:
                    drop_amount = new_savings - old_savings
                    try:
                        import subprocess
                        msg = f"Price dropped ${drop_amount:.0f}! {flight['origin']}→{flight['destination']} is now ${cheapest:.0f}"
                        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Travel Planner Pro"'])
                    except Exception as e:
                        logger.error(f"Failed to send notification: {e}")

            logger.info(
                f"Price check: {flight['origin']}→{flight['destination']} "
                f"on {flight['departure_date']}: ${cheapest} "
                f"(booked: ${flight['booked_price']}, delta: ${flight['booked_price'] - cheapest:.0f})"
            )
            return updated
        else:
            logger.warning(f"No results for tracked flight {flight_id}")
            return flight

    except Exception as e:
        logger.error(f"Price check failed for flight {flight_id}: {e}")
        return None


def check_all_flights(db: TrackerDB) -> dict:
    """Check prices for all actively tracked flights.

    Returns summary of results.
    """
    db.expire_departed_flights()
    active = db.get_active_flights()

    checked = 0
    drops_found = 0
    total_new_savings = 0.0

    for flight in active:
        old_savings = flight.get("total_savings", 0)
        result = check_flight_price(db, flight["id"])
        if result:
            checked += 1
            new_savings = result.get("total_savings", 0)
            if new_savings > old_savings:
                drops_found += 1
                total_new_savings += (new_savings - old_savings)

    return {
        "checked": checked,
        "total_active": len(active),
        "drops_found": drops_found,
        "new_savings": total_new_savings,
    }
