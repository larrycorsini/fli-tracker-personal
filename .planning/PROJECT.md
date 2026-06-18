# Fli-Tracker

## What This Is

A personal fork of [punitarani/fli](https://github.com/punitarani/fli) — Python library for Google Flights (reverse-engineered API) at **v0.10.0** — extended with a FastAPI price-tracker web app (`app/`), hotel search, an automated multi-destination fare pipeline, and a public static dashboard at https://flights.larrycorsini.com.

## Core Value

The personal tracker app and local workflows keep working while the underlying `fli` library stays current with upstream improvements (booking links, API fixes, CI).

## Current State (v1.1 shipped 2026-06-18)

**Shipped:** Multi-Destination Tracker — two-phase search across 8 regions, daily automation, Netlify static site with booking deep-links.

| Area | Status |
|------|--------|
| Multi-dest pipeline | ✅ `find_direct.py` → `best_direct.json` → `generate_flight_report.py` |
| Public dashboard | ✅ https://flights.larrycorsini.com (index, heatmap, history) |
| Daily automation | ✅ `daily_flight_search.sh` (launchd ~6 AM) |
| Price alerts | ✅ `alert.py` (iMessage thresholds) |
| FastAPI tracker app | ✅ Works; booking links not wired in API/UI yet |
| Fork Polish (cleanup/tests) | ⚠️ Deferred to next milestone |

See `.planning/milestones/v1.1-ROADMAP.md`.

## Requirements

### Validated

- ✓ Google Flights search via CLI — v0.10.0 with `booking_url`
- ✓ MCP server — expanded upstream tools
- ✓ FastAPI tracker app — flight/date/hotel search, tracker CRUD
- ✓ SQLite price tracking — background checks
- ✓ Merge upstream without losing tracker — v1.0
- ✓ Multi-destination automated search — v1.1
- ✓ Static Netlify dashboard with booking links — v1.1
- ✓ Daily pipeline + regional alerts — v1.1

### Active

Start next milestone with `/gsd-new-milestone`. Likely focus: Fork Polish tech debt (hot_core refactor, `tests/app/`, FastAPI booking links).

### Out of Scope

- fli-js frontend integration — evaluate later
- PyPI/npm publishing — upstream process
- Deleting local JSON trip snapshots — user data
- Live `tests/search/` in CI — remain flaky

## Context

**Git remotes:**
- `origin` → upstream `punitarani/fli`
- `personal` → `larrycorsini/fli-tracker-personal.git`

**Home airports:** SLC, PVU  
**Regions tracked:** DFW, California Coast, Georgia, Cancun, El Salvador, Europe, Japan, South Korea  
**Points model:** Chase Sapphire Preferred at 1.25¢ redemption in generated HTML

## Constraints

- **Compatibility:** `app/engine.py` must keep working with `fli` search APIs
- **Data:** `app/data/tracker.db` stays gitignored
- **Testing:** Live `tests/search/` remain flaky in CI
- **Carriers:** Exclude F9, MX, NK, G4, SY, XP from automated searches

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge upstream into local main (not rebase) | Preserve history; easy rollback | ✓ Good — v1.0 |
| Rescope v1.1 to Multi-Destination Tracker | Deliver automated public dashboard | ✓ Good — v1.1 |
| Static site for booking links vs FastAPI UI | Faster ship; Netlify already deployed | ✓ Good — defer FEAT-01–03 |
| Exclude budget carriers | User preference for mainline fares | ✓ Good |
| Defer Fork Polish to next milestone | Pipeline was higher priority | Pending |

## Evolution

<details>
<summary>Prior milestones (archived)</summary>

**v1.0 Upstream Sync** (2026-05-30): Merged upstream, verified tracker. [Archive](milestones/v1.0-ROADMAP.md)

**v1.1 Multi-Destination Tracker** (2026-06-18): Two-phase search, Netlify site. [Archive](milestones/v1.1-ROADMAP.md)

</details>

---
*Last updated: 2026-06-18 after v1.1 milestone*
