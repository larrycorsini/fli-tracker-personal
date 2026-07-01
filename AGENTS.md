# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Fli is a Python library providing programmatic access to Google Flights data via reverse-engineered API. It offers a CLI (`fli`), MCP server (`fli-mcp` / `fli-mcp-http`), and Python API. No external services (databases, caches, etc.) are required.

### Development commands

All standard commands are in the `Makefile` and `CLAUDE.md`. Key ones:

- **Install deps**: `uv sync --all-extras`
- **Lint**: `make lint` (ruff)
- **Format**: `make format`
- **Tests**: `make test` (standard), `make test-all` (including fuzz)
- **CLI**: `uv run fli flights JFK LAX 2026-05-15`
- **MCP HTTP server**: `uv run fli-mcp-http` (serves at `http://127.0.0.1:8000/mcp/`)

### Testing caveats

- Tests under `tests/search/` hit the live Google Flights API and are rate-limited (HTTP 429). These will frequently fail in cloud/CI environments. All other tests (CLI, core, models, MCP) are self-contained and pass reliably.
- Run `uv run pytest -vv --ignore=tests/search/` to skip flaky API-dependent tests.
- One MCP test (`test_search_dates_round_trip`) also makes a live API call and may fail with empty results.

### Releasing

Releases are manual: GitHub Actions → **Release** → Run workflow on `main`,
choose `bump=patch|minor|major|explicit`. Run with `dry_run=true` first to
preview. Bump logic is in `scripts/bump_version.py` (testable). See the
Releasing section in `CLAUDE.md` and the `.github/workflows/release*.yml`
workflows for the full process.

### MCP server notes

- The MCP HTTP endpoint requires `Accept: application/json, text/event-stream` header.
- The `fli/server/` module has been removed from the codebase.
- `fli-mcp-http` and the FastAPI tracker (`uvicorn app.server:app`) both default to port `8000`, so they cannot run at the same time on the default port. Override the MCP server with `HOST=127.0.0.1 PORT=8010 uv run fli-mcp-http` (it reads `HOST`/`PORT`) to run it alongside the tracker.
- Deploy profile for `fli-tracker`: use `nixpacks-tracker.toml` (starts `fli-tracker` on port 8000). Default `nixpacks.toml` still targets `fli-mcp-http`.

## Learned User Preferences

- When recommending flights, always include clickable booking links: per-itinerary `booking_url` from `fli flights --format json` (deep link), plus top-level search `booking_url` when useful. Never list fares without a buy link.
- Model the tracker web UI after Google Flights: clear layout, readable typography, accessible controls, and familiar search/filter flow; brand primary `#1F2A37`, accent Google blue `#1A73E8` (see UI-SPEC).
- Keep the dashboard hero as aviation photo with gradient overlay (not gradient-only); keep hero/subtitle copy generic site-wide, not tied to the active destination tab.
- Keep premium deals in a standalone "Premium deals from SLC" feed with client-side filters — do not merge into the nine region tabs.
- Show disabled pills for empty deal-board regions (e.g. Cancun with no fares); do not hide the region.
- Include weekday abbreviations beside dates in flight reports (e.g. Wed, Thu, Fri).
- Do not auto-push to the `personal` remote; wait for explicit user approval before publishing fork changes (user typically approves when closing milestones).
- Use `uv` on PATH in scripts and subprocess calls — avoid hardcoded absolute paths to a local `uv` binary.
- Exclude budget/low-cost carriers (Frontier F9, Breeze MX, Spirit NK, Allegiant G4, Sun Country SY, Avelo XP) from flight searches and recommendations.
- On mobile viewports, compact nav after scroll hides Heatmap and Trends links to preserve header space.
- Show multiple flight time/price options per region on the dashboard (not a single fare per destination).
- When the user asks about "the site" or Fli-Tracker dashboard, they mean https://flights.larrycorsini.com (static Netlify: Heatmap, Trends, Weekend Escapes), not Travel Planner Pro or the local FastAPI UI (`uvicorn app.server`).

## Learned Workspace Facts

- Personal fork of [punitarani/fli](https://github.com/punitarani/fli) extended with a FastAPI price-tracker in `app/`, hotel search, multi-destination pipeline, and Netlify site `flights-larrycorsini` (https://flights.larrycorsini.com) that auto-deploys committed `public/` from GitHub `larrycorsini/fli-tracker-personal` `main`; `best_direct.json` is gitignored and generated locally. Custom domain DNS is manual in Cloudflare (`flights` CNAME → `flights-larrycorsini.netlify.app`); Netlify does not auto-update external DNS.
- Git remotes: `origin` → upstream `punitarani/fli`; `personal` → `larrycorsini/fli-tracker-personal`; v1.1 milestone tagged on `personal`.
- Hotel search lives in `app/hotels.py` (successor to removed root `hot_core.py`).
- Upstream can return `FlightResult` entries with `price=None`; `app/engine.py` must skip or safely sort unpriced rows.
- Tracker app entry point: `uv run uvicorn app.server:app --reload`; flight search streams via SSE at `/api/search/flights`.
- Local SQLite tracker data lives in `app/data/tracker.db` (gitignored); history/trends pages query `search_history` by region name plus legacy destination airport codes.
- Home airports for trip searches and the automated tracker are SLC and PVU.
- `tracker_config.py` holds shared pipeline config: `REGIONS`, alert thresholds, `EXCLUDED_AIRLINES`, `SITE_URL`, two-phase search constants, and premium-deal settings (`PREMIUM_*`). `find_deals.py` is the second pipeline: SLC/PVU-origin premium-cabin discovery (BUSINESS/PREMIUM_ECONOMY) over curated destinations; writes `premium-deals.json` and `public/data/premium-deals.json`, preserving prior deals on empty runs like `find_direct.py`. Automated `find_direct.py` outbound windows: domestic departs day+14…+74 (3/4-night trips), international day+14…+42 (7/10-night trips); nothing inside 14 days.
- Daily automated flight search: launchd job `com.larry.fli-tracker.daily-search` (~6 AM, plist in `~/Library/LaunchAgents/`) runs via `~/.local/bin/fli-tracker-daily-search.sh` → `daily_flight_search.sh` in `~/Projects/Fli-tracker` (relocated from `~/Documents/Projects/Fli-tracker` because macOS TCC blocks launchd cwd/script exec under `~/Documents`—exit 126 “Operation not permitted”; a `~/.local/bin` wrapper still fails if it execs scripts in Documents) → `find_direct.py --force` (`--test` for smoke runs) → `find_deals.py` (non-fatal on failure) → `alert.py` → `generate_flight_report.py` → `public/` (must `git add public/data/flights.json` and `public/data/premium-deals.json`) → git push `personal`/`main`; logs in `logs/daily_flight_search.log`. `find_direct.py` and `generate_flight_report.py` preserve prior fare data when a run returns zero flights (empty Google Flights API days). Manual catch-up: run `./daily_flight_search.sh` in Terminal.app if launchd fails.
- `tracker_io.py` provides shared atomic JSON/text writes for pipeline artifacts (`find_direct.py`, `find_deals.py`, `generate_flight_report.py`, `alert.py`).
- `alert.py` requires `FLI_ALERT_PHONE` env var and skips alerts when unset (no hardcoded phone fallback). Scheduled runs get it from the launchd plist `EnvironmentVariables`; manual Terminal runs must `export FLI_ALERT_PHONE` first.
- Premium award enrichment uses seats.aero Partner API cached search only (`seats_aero_client.py`); `SEATS_AERO_API_KEY` in gitignored `.env` for manual runs and in the launchd plist `EnvironmentVariables` for scheduled runs (launchd does not read `.env`). Budget ~10 cached calls per daily run with a 950/day soft cap (50 reserved). Chase Sapphire Preferred portal estimate (1.25¢) is the fallback when seats.aero is unavailable or finds no award.
