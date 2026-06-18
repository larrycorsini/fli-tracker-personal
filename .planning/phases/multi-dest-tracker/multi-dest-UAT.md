---
status: testing
phase: multi-dest-tracker
source:
  - public/index.html
  - public/heatmap.html
  - public/history.html
  - find_direct.py
  - generate_flight_report.py
  - daily_flight_search.sh
  - best_direct.json
started: 2026-06-18T22:30:00Z
updated: 2026-06-18T22:30:00Z
auto_verified: 10
---

## Current Test

number: 1
name: Live Site Loads
expected: |
  Open https://flights.larrycorsini.com/ in a browser. The page loads without errors, shows the Fli-Tracker hero ("Track your next adventure"), navigation links to Heatmap and Trends, and the flight options section with destination tabs.
awaiting: user response

## Tests

### 1. Live Site Loads
expected: Open https://flights.larrycorsini.com/ — page loads with hero, nav, and destination tabs (no blank page or error).
result: [pending]

### 2. Multiple Destination Tabs
expected: Homepage shows 8 destination tabs — DFW, California Coast, Georgia, Cancun, El Salvador, Europe, Japan, South Korea.
result: pass
auto_note: Verified in public/index.html — 8 role='tab' buttons present.

### 3. Region Has Many Fare Groups
expected: Each populated region (e.g. DFW, Europe) shows many airline/date fare rows, not a single dummy row.
result: pass
auto_note: best_direct.json — DFW 184, California Coast 78, Georgia 182, Europe 866, Japan 569, South Korea 457 flights.

### 4. Date Day Abbreviations
expected: Fare date lines show weekday abbreviations like Wed, Thu, Fri (not bare ISO dates only).
result: pass
auto_note: 2785 Wed/Thu/Fri occurrences in generated public/index.html.

### 5. Best Deals Right Now
expected: Deal board section above tabs lists regions with lowest prices (e.g. California Coast $198, DFW $295).
result: pass
auto_note: "Best Deals Right Now" section with 7 region price pills in public/index.html.

### 6. Last Updated Timestamp
expected: Hero section shows a recent "Last updated" date/time stamp.
result: pass
auto_note: "Last updated: Thu, Jun 18, 2026 at 03:17 PM" in public/index.html; best_direct.json mtime 2026-06-18 15:17.

### 7. Booking URLs in Generated HTML
expected: Generated HTML embeds Google Flights booking deep-links (google.com/travel/flights).
result: pass
auto_note: 2414 google.com/travel/flights URLs in public/index.html.

### 8. Cancun Tab Empty State
expected: Cancun tab is present; when selected it shows an empty-state message (no fares) rather than broken layout.
result: pass
auto_note: Tab exists; panel shows "No flights found for Cancun." — best_direct.json Cancun count 0.

### 9. Two-Phase Search Data Pipeline
expected: find_direct.py two-phase search produces multi-region JSON consumed by the report generator (not stale single-destination data).
result: pass
auto_note: best_direct.json contains all 8 regions with fresh mtime; find_direct.py implements phase 1 shortlist + phase 2 flight searches.

### 10. Heatmap Region Selectors Present
expected: heatmap.html includes region selector buttons for all destination regions.
result: pass
auto_note: 8 activeRegion buttons in public/heatmap.html with embedded heatmapData per region.

### 11. History Region Selectors Present
expected: history.html includes region selector buttons for all destination regions.
result: pass
auto_note: 8 activeRegion buttons in public/history.html.

### 12. Tab Switching Updates Flight List
expected: Clicking a destination tab (e.g. Europe, Japan) switches the visible fare list to that region's flights; heading updates to "Flight Options for {region}".
result: [pending]

### 13. Price and Airline Filters
expected: Show Filters reveals max-price slider and airline dropdown; adjusting them hides fares above max price or from other airlines.
result: [pending]

### 14. Scroll-to-Top Button
expected: After scrolling down past ~400px, a scroll-to-top button appears; clicking it smoothly scrolls back to the top.
result: [pending]

### 15. Expand Row Shows Time Options with Book Links
expected: Clicking a fare row expands it to show individual departure times, each with a Book link.
result: [pending]

### 16. Book Link Opens Google Flights
expected: Clicking a Book link opens Google Flights booking page for that specific itinerary in a new tab.
result: [pending]

### 17. Heatmap Calendar Renders Per Region
expected: On heatmap.html, switching regions updates the calendar grid with colored price cells for that region's dates.
result: [pending]

### 18. History Chart Loads Per Region
expected: On history.html (Trends), switching regions renders a 14-day price trend chart for the selected region.
result: [pending]

### 19. Deal Board Pills Jump to Region Tab
expected: Clicking a pill in "Best Deals Right Now" (e.g. California Coast $198) switches the active destination tab to that region.
result: [pending]

## Summary

total: 19
passed: 10
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps

[none yet]
