#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime, timedelta
from app.hotels import search_hotels_core

def get_best_flight(origin, dest, depart, ret_date):
    """Uses fli to get the single cheapest nonstop flight."""
    try:
        cmd = [
            "uv", "run", "fli", "flights",
            origin, dest, depart, "-r", ret_date,
            "--stops", "NON_STOP", "--format", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        flights = data.get("flights", [])
        if not flights:
            return None
            
        # Sort by price
        flights.sort(key=lambda x: x["price"])
        return flights[0]
    except Exception:
        return None

def main():
    origin = "PVU"
    dest = "DFW"
    city_name = "Dallas TX"
    
    # Let's check a few trip lengths centered around late April
    trips = [
        {"start": "2026-04-18", "end": "2026-04-23"}, # 5 day
        {"start": "2026-04-19", "end": "2026-04-24"}, # 5 day
        {"start": "2026-04-20", "end": "2026-04-25"}  # 5 day
    ]
    
    print(f"🌍 TRIPLE THREAT TRAVEL PLANNER: {origin} -> {dest}")
    print("="*80)
    print(f"{'DATES':<25} | {'FLIGHT':<10} | {'HOTEL':<10} | {'TOTAL':<10} | {'HOTEL NAME'}")
    print("-" * 80)

    for trip in trips:
        start = trip["start"]
        end = trip["end"]
        dates_label = f"{start} to {end}"
        
        # 1. Get Flight
        flight = get_best_flight(origin, dest, start, end)
        f_price = flight["price"] if flight else 0
        
        # 2. Get Hotels
        hotels = search_hotels_core(city_name, start, end)
        h_best = hotels[0] if hotels else None
        
        if not flight or not h_best:
            print(f"{dates_label:<25} | {'ERROR':<10} | {'ERROR':<10} | {'N/A':<10} | Skipping...")
            continue
            
        h_price_total = float(h_best["total_price"].replace("$", "").replace(",", "")) if h_best["total_price"] != "N/A" else 0
        total = f_price + h_price_total
        
        h_name = h_best["name"][:30] + "..." if len(h_best["name"]) > 33 else h_best["name"]
        
        print(f"{dates_label:<25} | ${f_price:<9.0f} | ${h_price_total:<9.0f} | ${total:<9.0f} | {h_name}")

    print("="*80)

if __name__ == "__main__":
    main()
