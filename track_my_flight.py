#!/usr/bin/env python3
import csv
import os
import json
import subprocess
from datetime import datetime

# --- CONFIGURATIONS ---
TRACKED_TRIPS = [
    {
        "name": "Trip 1: May 19-20 (May Pivot)",
        "origin": "PVU",
        "destination": "DFW",
        "depart": "2026-05-19",
        "return": "2026-05-20",
        "return_before": None, # No deadline
        "url": "https://www.google.com/travel/flights/search?tfs=CBwQAhogEgoyMDI2LTA1LTE5KABqBwgBEgNQVlVyBwgBEgNERlcaIBIKMjAyNi0wNS0yMCgAagcIARIDREZXcgcIARIDUFZVQAFIAXABggELCP___________wGYAQE"
    },
    {
        "name": "Trip 2: Apr 7-14 (Original Window)",
        "origin": "PVU",
        "destination": "DFW",
        "depart": "2026-04-07",
        "return": "2026-04-14",
        "return_before": "19:00", # Must arrive back before 7:00 PM MST
        "url": "https://www.google.com/travel/flights/search?tfs=CBwQAhogEgoyMDI2LTA0LTA3KABqBwgBEgNQVlVyBwgBEgNERlcaIBIKMjAyNi0wNC0xNCgAagcIARIDREZXcgcIARIDUFZVQAFIAXABggELCP___________wGYAQE"
    },
    {
        "name": "Trip 3: Apr 7-14 (SLC Alternative)",
        "origin": "SLC",
        "destination": "DFW",
        "depart": "2026-04-07",
        "return": "2026-04-14",
        "return_before": "19:00", # Must arrive back before 7:00 PM MST
        "url": "https://www.google.com/travel/flights/search?tfs=CBwQAhogEgoyMDI2LTA0LTA3KABqBwgBEgNTV0VyBwgBEgNERlcaIBIKMjAyNi0wNC0xNCgAagcIARIDREZXcgcIARIDU0xDUAFIAXABggELCP___________wGYAQE"
    }
]

LOG_FILE = "flight_price_log.csv"

def check_trip(trip):
    """Uses the fli CLI to check a specific trip with time constraints."""
    try:
        cmd = [
            "uv", "run", "fli", "flights", 
            trip["origin"], trip["destination"], trip["depart"], 
            "-r", trip["return"], 
            "--stops", "NON_STOP", 
            "--format", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        if not data.get("success") or not data.get("flights"):
            return None
        
        # Filter by return time if applicable
        valid_flights = []
        for f in data["flights"]:
            if trip["return_before"]:
                # arrival_time format: "2026-04-14T13:32:00"
                arrival_str = f["return"]["legs"][-1]["arrival_time"]
                arrival_time = arrival_str.split("T")[1][:5] # "13:32"
                if arrival_time > trip["return_before"]:
                    continue # Too late
            valid_flights.append(f)
            
        if not valid_flights:
            return None
            
        # Return the cheapest valid flight
        best = min(valid_flights, key=lambda x: x["price"])
        return {
            "price": best["price"],
            "out_airline": best["outbound"]["legs"][0]["airline"]["name"],
            "ret_airline": best["return"]["legs"][0]["airline"]["name"],
            "arrival": best["return"]["legs"][-1]["arrival_time"].split("T")[1][:5]
        }
    except Exception:
        return None

def log_price(trip_name, data):
    """Logs the flight data to a CSV file."""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Trip Name", "Price", "Airline Out", "Airline Ret", "Arrival Back"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            trip_name, 
            data['price'], 
            data['out_airline'], 
            data['ret_airline'],
            data['arrival']
        ])

def main():
    print(f"🚀 Starting Dashboard Flight Check...")
    print(f"----------------------------------------")
    
    for trip in TRACKED_TRIPS:
        print(f"🔍 Checking {trip['name']}...")
        result = check_trip(trip)
        
        if result:
            print(f"✅ Found: ${result['price']:.2f} | Arrives: {result['arrival']} | Airlines: {result['out_airline']}/{result['ret_airline']}")
            log_price(trip["name"], result)
        else:
            print(f"❌ No matching nonstop flights found (check time constraints).")
        
        print(f"🔗 URL: {trip['url']}")
        print(f"----------------------------------------")

if __name__ == "__main__":
    main()
