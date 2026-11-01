# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Fli is a Python library providing programmatic access to Google Flights data via reverse-engineered API. It offers a CLI (`fli`), MCP server (`fli-mcp` / `fli-mcp-http`), and Python API. No external services (databases, caches, etc.) are required.

### Development commands

All standard commands are in the `Makefile` and `CLAUDE.md`. Key ones:

- **Install deps**: `uv sync --all-extras`
- **Lint**: `make lint` (ruff)
- **Format**: `make format`
- **Tests**: `make test` (standard, offline), `make test-all` (including fuzz, still offline), `make test-live` (small stable live set, real network), `make test-live-fuzz` (adds the noisier fuzz-gated live test, opt-in only)
- **CLI**: `uv run fli flights JFK LAX 2026-05-15`
- **MCP HTTP server**: `uv run fli-mcp-http` (serves at `http://127.0.0.1:8000/mcp/`)

### Testing caveats

- Almost all tests, including most of `tests/search/`, run entirely offline against captured
  fixtures/stubs — no network access is required and none of them are rate-limited.
- A small number of tests are marked `live` because they call the real Google Flights API:
  `test_search_flights_new_filters_live.py`, the parametrized case in
  `test_search_flights_fuzz.py`, the four search tests in
  `tests/mcp/test_mcp_server.py::TestMCPServer`, and a handful of previously-unmocked cases in
  `test_search_flights.py` / `test_search_dates.py`. These are skipped unless `--live` is passed
  (`--all` does **not** enable them), so `make test` / `make test-all` never hit the network.
  `--fuzz`, `--live` and `--all` are independent skip-only gates: a test needs *every* gate that
  applies to it passed together (the fuzz-gated live case needs both `--all`/`--fuzz` *and*
  `--live` at once — `-m live --live` alone silently drops it from collection).
  Run `make test-live` (`pytest -m live --live`, no `--all`) for the small, stable live set if you
  have network access — the same set that runs daily in `.github/workflows/live-canary.yml`,
  which retries one failed batch after a short pause before filing/updating a GitHub issue.
  `make test-live-fuzz` additionally runs the 100-case fuzz-gated live test, which is noticeably
  flakier under its back-to-back burst (~11% per-case failures measured) and is opt-in only —
  never scheduled. Any of these may skip on a transient transport failure but fail on an actual
  regression.

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

- When recommending flights, always include clickable booking links: per-itinerary `booking_url` from `fli flights --format json` (Google `tfs=` deep link), plus top-level search `booking_url` when useful. Never list fares without a buy link. Premium deals Book must use itinerary `booking_url`, not dashboard `?tab=` links.
- Model the tracker web UI after Google Flights: clear layout, readable typography, accessible controls, and familiar search/filter flow; brand primary `#1F2A37`, accent Google blue `#1A73E8` (see UI-SPEC).
- Keep the dashboard hero as aviation photo with gradient overlay (not gradient-only); keep hero/subtitle copy generic site-wide, not tied to the active destination tab.
- Keep premium deals in a standalone "Premium deals from SLC" feed with client-side filters — do not merge into the nine region tabs. Prioritize cash round-trip fares for Book; treat points as secondary estimates.
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
- Tracker app: `uv run uvicorn app.server:app --reload`; flight search streams via SSE at `/api/search/flights`. Local SQLite data in `app/data/tracker.db` (gitignored); history/trends query `search_history` by region name plus legacy destination airport codes.
- Home airports for trip searches and the automated tracker are SLC and PVU.
- `tracker_config.py` holds shared pipeline config: `REGIONS`, alert thresholds, `EXCLUDED_AIRLINES`, `SITE_URL`, two-phase search constants, and premium-deal settings (`PREMIUM_*`). `find_deals.py` is the second pipeline: SLC/PVU-origin premium-cabin discovery (BUSINESS/PREMIUM_ECONOMY) over curated destinations; writes `premium-deals.json` and `public/data/premium-deals.json`, preserving prior deals on empty runs like `find_direct.py`. Automated `find_direct.py` outbound windows: domestic departs day+14…+74 (3/4-night trips), international day+14…+42 (7/10-night trips); nothing inside 14 days.
- Daily automated flight search: launchd job `com.larry.fli-tracker.daily-search` (~6 AM, plist in `~/Library/LaunchAgents/`) runs via `~/.local/bin/fli-tracker-daily-search.sh` → `daily_flight_search.sh` in `~/Projects/Fli-tracker` (relocated from `~/Documents/Projects/Fli-tracker` because macOS TCC blocks launchd cwd/script exec under `~/Documents`—exit 126 “Operation not permitted”; a `~/.local/bin` wrapper still fails if it execs scripts in Documents) → `find_direct.py --force` (`--test` for smoke runs) → `find_deals.py` (non-fatal on failure) → `alert.py` → `generate_flight_report.py` → `public/` (must `git add public/data/flights.json` and `public/data/premium-deals.json`) → git push `personal`/`main`; logs in `logs/daily_flight_search.log`. `find_direct.py` and `generate_flight_report.py` preserve prior fare data when a run returns zero flights (empty Google Flights API days). Manual catch-up: run `./daily_flight_search.sh` in Terminal.app if launchd fails.
- `tracker_io.py` provides shared atomic JSON/text writes for pipeline artifacts (`find_direct.py`, `find_deals.py`, `generate_flight_report.py`, `alert.py`).
- `alert.py` requires `FLI_ALERT_PHONE` env var and skips alerts when unset (no hardcoded phone fallback). Scheduled runs get it from the launchd plist `EnvironmentVariables`; manual Terminal runs must `export FLI_ALERT_PHONE` first. iMessage body (`alert_format.py`) uses short `flights.larrycorsini.com` tab links only—AppleScript cannot hide URLs behind link text; email uses HTML Book buttons.
- Premium award enrichment uses seats.aero Partner API cached search only (`seats_aero_client.py`); cached search returns one-way award rows (RT point totals are heuristic). Cash premium deals from Google Flights are the bookable round-trip path (`booking_url` with `tfs=`). `SEATS_AERO_API_KEY` in gitignored `.env` for manual runs and in the launchd plist `EnvironmentVariables` for scheduled runs (launchd does not read `.env`). Budget ~10 cached calls per daily run with a 950/day soft cap (50 reserved). Chase Sapphire Preferred portal estimate (1.25¢) is the fallback when seats.aero is unavailable or finds no award.
