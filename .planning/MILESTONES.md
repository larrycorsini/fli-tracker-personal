# Milestones

## v1.1 Multi-Destination Tracker (Shipped: 2026-06-18)

**Phases:** 1 (multi-dest-tracker) | **Requirements:** 11 shipped, 12 deferred (Fork Polish)

**Delivered:** Automated two-phase flight search across 8 regions from SLC/PVU, daily launchd pipeline, iMessage price alerts, and static Netlify dashboard with per-itinerary Google Flights booking deep-links.

**Key accomplishments:**

- `find_direct.py` — SearchDates shortlist + SearchFlights detail with retries and atomic JSON write
- `tracker_config.py` — 8 regions, excluded budget carriers, alert thresholds
- `generate_flight_report.py` — Alpine.js + Tailwind static HTML (index, heatmap, history)
- `daily_flight_search.sh` — search → alert → report → Netlify deploy
- Live site: https://flights.larrycorsini.com

### Known Gaps

Original Fork Polish scope (phases 5–8) deferred as tech debt:

- CLEAN-01–03: `hot_core.py` refactor, `flight_gui.py` archive
- TEST-01–04: `tests/app/` coverage
- FEAT-01–03: FastAPI booking links in `app/static/app.js`
- QA-01: lint re-verification

Known deferred items at close: 1 (see STATE.md Deferred Items — UAT live site check)

**Archives:**

- [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md)
- [v1.1-phases/](milestones/v1.1-phases/)

**Git tag:** `v1.1`

---

## v1.0 Upstream Sync (Shipped: 2026-05-30)

**Phases:** 4 | **Requirements:** 15/15 complete

**Delivered:** Merged 31 upstream commits from punitarani/fli into personal fork at `flights` 0.10.0. Tracker app, CLI, MCP, and hotel search verified. Local customizations preserved.

**Key accomplishments:**

- Clean merge of `origin/main` with rollback tag `pre-upstream-v1.0`
- Fixed `app/engine.py` for upstream `FlightResult` entries with null prices
- Full app smoke test: FastAPI search, tracker CRUD, hotels API
- 433 tests passing, lint clean; merge documented in `MERGE-SUMMARY.md`

**Archives:**

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)

**Git tag:** `v1.0`

---

## Pre-GSD History

Personal fork developed locally with:

- FastAPI tracker app (`app/`)
- Hotel search via `hot_core.py`
- Root-level trip planning scripts
- Fork point at upstream commit `1cb0231`
