#!/usr/bin/env python3
import csv
import os
import json
import subprocess
from datetime import datetime

# --- CONFIGURATIONS ---
LOG_FILE = "flight_price_log.csv"

# Generate trips for 5, 6, and 7 day durations
# between April 17 and April 25 from PVU and SLC
TRACKED_TRIPS = []
for orig in ["PVU"]:
    for duration in [4, 5, 6]:  # e.g. 4 equates to 5 days (17 to 21 inclusive)
        for start_day in range(17, 26):
            end_day = start_day + duration
            if end_day <= 25:
                # duration 4 = 5-Day Trip, duration 5 = 6-Day Trip, duration 6 = 7-Day Trip
                TRACKED_TRIPS.append({
                    "name": f"{orig} {duration + 1}-Day (Apr {start_day}-{end_day})",
                    "origin": orig,
                    "destination": "DFW",
                    "depart": f"2026-04-{start_day:02d}",
                    "return": f"2026-04-{end_day:02d}",
                    "url": f"https://www.google.com/travel/flights?q=Flights%20to%20DFW%20from%20{orig}%20on%202026-04-{start_day:02d}%20through%202026-04-{end_day:02d}&nonstop=1"
                })

def check_trip(trip):
    """Uses the fli CLI to check a specific trip with time constraints."""
    try:
        cmd = [
            "/Users/larry/.local/bin/uv", "run", "fli", "flights", 
            trip["origin"], trip["destination"], trip["depart"], 
            "-r", trip["return"], 
            "--stops", "NON_STOP", 
            "--format", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        valid_flights = data.get("flights", [])
        if not valid_flights:
            return None
            
        # Filter strictly for American Airlines
        aa_flights = []
        for f in valid_flights:
            out_airline = f["outbound"]["legs"][0]["airline"]["name"]
            ret_airline = f["return"]["legs"][0]["airline"]["name"]
            if "American" in out_airline and "American" in ret_airline:
                aa_flights.append(f)
                
        if not aa_flights:
            return None
            
        valid_flights = aa_flights
            
        # Add outbound departure time for sorting
        for f in valid_flights:
            f["_out_dep_time"] = f["outbound"]["legs"][0]["departure_time"]
            
        # We want cheapest flights, leaving as early as possible
        valid_flights.sort(key=lambda x: (x["price"], x["_out_dep_time"]))
        
        # Pick the best valid flight
        best = valid_flights[0]

        out_dep_time = best["outbound"]["legs"][0]["departure_time"].split("T")[1][:5]
        ret_arr_time = best["return"]["legs"][-1]["arrival_time"].split("T")[1][:5]

        return {
            "price": best["price"],
            "out_airline": best["outbound"]["legs"][0]["airline"]["name"],
            "ret_airline": best["return"]["legs"][0]["airline"]["name"],
            "out_depart": out_dep_time,
            "ret_arrive": ret_arr_time
        }
    except Exception:
        return None

def log_prices(results):
    """Logs the flight data to a CSV file."""
    if not results:
        return
        
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Trip Name", "Price", "Airline Out", "Airline Ret", "Out Depart", "Ret Arrive"])
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for res in results:
            writer.writerow([
                timestamp, 
                res["trip"]["name"], 
                res['price'], 
                res['out_airline'], 
                res['ret_airline'],
                res['out_depart'],
                res['ret_arrive']
            ])

def main():
    print(f"🚀 Starting Dashboard Flight Check (Scanning {len(TRACKED_TRIPS)} date combinations)...")
    print(f"--------------------------------------------------")
    
    results = []
    
    for trip in TRACKED_TRIPS:
        # Pad strings for a clean progress look
        print(f"🔍 Checking {trip['name']:<25} ... ", end="", flush=True)
        result = check_trip(trip)
        
        if result:
            print(f"✅ ${result['price']:.0f}")
            result["trip"] = trip
            results.append(result)
        else:
            print(f"❌ None")

    if not results:
        print("\n❌ No nonstop flights found for any of the trip parameters.")
        return

    # Sort results cheapest to least cheap
    results.sort(key=lambda x: x["price"])
    
    # Save best prices to log
    log_prices(results)
    
    print("\n" + "🌟 " * 25)
    print("🏆 BEST NONSTOP FLIGHTS (Cheapest to Most Expensive) 🏆")
    print("🌟 " * 25 + "\n")
    
    for rank, res in enumerate(results, 1):
        trip = res["trip"]
        print(f"{rank:2d}. {trip['name']:<25} 💵 ${res['price']:.2f}")
        print(f"    🛫 Leave to DFW:  {res['out_depart']} ({res['out_airline']})")
        print(f"    🛬 Arrive back:   {res['ret_arrive']} ({res['ret_airline']})")
        print(f"    🔗 {trip['url']}")
        print("-" * 65)

if __name__ == "__main__":
    main()
