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

## Learned User Preferences

- When recommending flights, always include clickable booking links: per-itinerary `booking_url` from `fli flights --format json` (deep link), plus top-level search `booking_url` when useful. Never list fares without a buy link.
- Model the tracker web UI after Google Flights: clear layout, readable typography, accessible controls, and familiar search/filter flow.
- Do not auto-push to the `personal` remote; wait for explicit user approval before publishing fork changes.
- Use `uv` on PATH in scripts and subprocess calls — avoid hardcoded absolute paths to a local `uv` binary.
- Exclude budget/low-cost carriers (Frontier F9, Breeze MX, Spirit NK, Allegiant G4, Sun Country SY, Avelo XP) from flight searches and recommendations.

## Learned Workspace Facts

- Personal fork of [punitarani/fli](https://github.com/punitarani/fli) extended with a FastAPI price-tracker in `app/`, hotel search, and local trip-planning scripts.
- Git remotes: `origin` → upstream `punitarani/fli`; `personal` → `larrycorsini/fli-tracker-personal`.
- `hot_core.py` at the repo root is imported via a `sys.path` hack; planned refactor moves it to `app/hotels.py`.
- Upstream can return `FlightResult` entries with `price=None`; `app/engine.py` must skip or safely sort unpriced rows.
- Tracker app entry point: `uv run uvicorn app.server:app --reload`; flight search streams via SSE at `/api/search/flights`.
- Local SQLite tracker data lives in `app/data/tracker.db` and stays gitignored.
- Home airports for trip searches and the automated tracker are SLC and PVU.
- Daily automated flight search: `find_direct.py` → `best_direct.json` → `generate_flight_report.py` → static HTML in `public/`, deployed to Netlify via `daily_flight_search.sh` (launchd ~6 AM).
- Automated tracker optimizes for Chase Sapphire Preferred points (1.25¢ redemption); multi-region destinations are configured in `REGIONS` inside `find_direct.py`.
