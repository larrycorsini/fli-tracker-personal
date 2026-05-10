from fastmcp import FastMCP
from hot_core import search_hotels_core

app = FastMCP("Google Hotels Search")

@app.tool()
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """
    Search for hotels via Google Hotels native API representation.
    
    Args:
        city: The destination city (e.g. "Dallas TX")
        checkin: Check-in date (e.g. "2026-05-10")
        checkout: Check-out date (e.g. "2026-05-15")
    """
    try:
        hotels = search_hotels_core(city, checkin, checkout)
        
        if not hotels:
            return "No hotels found or error occurred."
            
        output = [f"Found {len(hotels)} hotels in {city}:", ""]
        
        for h in hotels:
            rating_str = f", Rating: {h['rating']}" if h['rating'] != "N/A" else ""
            output.append(f"- {h['name']}: {h['price_per_night']} per night ({h['total_price']} total){rating_str}")
            
        return "\\n".join(output)
        
    except Exception as e:
        return f"Error executing native search: {str(e)}"

if __name__ == "__main__":
    app.run()
