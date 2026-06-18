# Codebase Structure

**Analysis Date:** 2026-06-18

## Directory Layout

```
Fli-tracker/
├── fli/                    # Core Python library (PyPI package "flights")
│   ├── cli/                # Typer CLI: flights, dates, airports, multi
│   ├── core/               # Shared parsers, builders, links, currency
│   ├── mcp/                # FastMCP server + STDIO/HTTP entry
│   ├── models/             # Airport/Airline enums, Google Flights Pydantic models
│   └── search/             # SearchFlights, SearchDates, HTTP client, decoders
├── app/                    # Personal fork — FastAPI price tracker + SPA
│   ├── static/             # Tracker UI (index.html, app.js, styles.css)
│   ├── data/               # SQLite DB + airports_lite.json (gitignored: tracker.db)
│   ├── server.py           # FastAPI entry, routes, SSE, lifespan
│   ├── engine.py           # fli wrappers, streaming, serialization
│   ├── tracker.py          # SQLite tracker + refund policies
│   ├── hotels.py           # Google Hotels search (formerly hot_core.py)
│   ├── airport_data.py     # Airport autocomplete for tracker
│   └── models.py           # Pydantic enums (mostly documentation; routes use inline models)
├── fli-js/                 # TypeScript port (npm package "fli-js")
│   ├── src/                # core/, models/, search/ — mirrors fli/ layout
│   ├── tests/              # Bun tests
│   └── scripts/            # generate-enums.ts
├── tests/                  # pytest — mirrors fli/ structure + app-adjacent scripts
├── scripts/                # Release/maintenance: bump_version, update_airports, capture_fixtures
├── examples/               # python/ and typescript/ usage samples
├── docs/                   # MkDocs site (upstream)
├── data/                   # airports.csv, airlines.csv — enum source data for fli
├── public/                 # Legacy static PWA (Netlify); separate from app/static
├── public_backup_*/        # Timestamped backup of public/ (local)
├── find_*.py, plan_trip.py # Ad-hoc trip-planning scripts (local, untracked)
├── scratch_*.py            # One-off experiments (local)
├── pyproject.toml          # Package config; scripts: fli, fli-mcp, fli-tracker
├── uv.lock                 # Python lockfile
├── Makefile                # test, lint, format, mcp, docs
└── .planning/              # GSD planning artifacts
```

## Directory Purposes

**`fli/`:**
- Purpose: Publishable Google Flights library
- Contains: CLI, MCP, search engine, models, core utilities
- Key files: `fli/search/flights.py`, `fli/search/client.py`, `fli/cli/main.py`, `fli/mcp/server.py`, `fli/core/parsers.py`, `fli/core/builders.py`

**`app/`:**
- Purpose: Personal price-tracker web app layered on `fli`
- Contains: FastAPI server, search wrappers, SQLite persistence, static SPA
- Key files: `app/server.py`, `app/engine.py`, `app/tracker.py`, `app/static/app.js`

**`fli-js/`:**
- Purpose: Independent TypeScript/npm distribution
- Contains: Parallel module structure to Python `fli/`
- Key files: `fli-js/src/search/flights.ts`, `fli-js/src/index.ts`, `fli-js/package.json`

**`tests/`:**
- Purpose: pytest suite; `tests/search/` hits live Google API (flaky in CI)
- Contains: `tests/cli/`, `tests/core/`, `tests/models/`, `tests/mcp/`, `tests/search/`, `tests/scripts/`
- Key files: `tests/conftest.py`, `tests/search/fixtures/*.bin`

**`scripts/`:**
- Purpose: Repo maintenance, not runtime
- Contains: `scripts/bump_version.py`, `scripts/update_airports.py`, `scripts/generate_enums.py`, `scripts/capture_fixtures.py`

**`examples/`:**
- Purpose: Documented API usage for Python and TypeScript consumers
- Contains: `examples/python/*.py`, `examples/typescript/*.ts`

**`public/`:**
- Purpose: Standalone static flight-curation PWA (Alpine.js + Tailwind CDN)
- Contains: `public/index.html`, `public/heatmap.html`, `public/history.html`, `public/sw.js`, `public/manifest.json`
- Note: Not mounted by `app/server.py`; deployed separately

**Root `*.py` scripts:**
- Purpose: Local trip research, reporting, alerts — developer utilities
- Contains: `find_direct.py`, `find_cheapest.py`, `plan_trip.py`, `generate_flight_report.py`, `flight_gui.py`, `hotels_mcp.py`, etc.
- Note: Not included in hatch wheel; keep out of upstream PRs unless intentionally contributing

## Key File Locations

**Entry Points:**
- `app/server.py`: FastAPI app + `main()` for `fli-tracker` CLI script
- `fli/cli/main.py`: `fli` Typer CLI (`fli/cli/__init__.py` exports `cli`)
- `fli/mcp/_entry.py`: `fli-mcp` / `fli-mcp-http` thin wrappers
- `fli/search/flights.py`: `SearchFlights` class — primary search API
- `fli-js/src/index.ts`: npm package public export

**Configuration:**
- `pyproject.toml`: Dependencies, scripts, hatch packages (`fli`, `app`), pytest/ruff config
- `Makefile`: `make test`, `make lint`, `make mcp-http`
- `uv.lock`: Locked Python deps
- `fli-js/biome.json`, `fli-js/tsconfig.json`: JS lint/build
- `railway.toml`, `nixpacks.toml`, `Dockerfile`: Deployment configs
- `.github/workflows/`: PyPI/npm release, docs, CI

**Core Logic:**
- `fli/search/flights.py`: Flight search orchestration
- `fli/search/dates.py`: Cheapest-date search
- `fli/search/client.py`: Rate-limited HTTP client
- `fli/search/_decoders.py`, `_wire.py`, `_urls.py`, `_proto.py`: Response parsing internals
- `fli/core/parsers.py`, `fli/core/builders.py`: Shared filter construction
- `app/engine.py`: Tracker-specific search orchestration + JSON serialization
- `app/tracker.py`: SQLite + price-check integration
- `app/hotels.py`: Hotel search (successor to removed root `hot_core.py`)

**Frontend (active tracker):**
- `app/static/index.html`: SPA shell, form markup, tab structure
- `app/static/app.js`: All client logic — SSE, tracker, trips, presets
- `app/static/styles.css`: Tracker styling

**Data files:**
- `app/data/tracker.db`: SQLite (gitignored) — tracker state
- `app/data/airports_lite.json`: Trimmed airport list for autocomplete
- `data/airports.csv`, `data/airlines.csv`: Source for `fli.models` enums

**Testing:**
- `tests/search/`: Live API tests + binary fixtures
- `tests/mcp/`: MCP tool unit/integration tests
- `tests/cli/`: CLI output and parsing tests
- `fli-js/tests/`: Bun unit/integration tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (`search_flights.py` pattern in commands, not files)
- Private search internals: leading underscore (`_decoders.py`, `_wire.py`, `_helpers.py`)
- CLI commands: verb nouns in `fli/cli/commands/` (`flights.py`, `dates.py`)
- Root scripts: `find_<goal>.py`, `scratch_<topic>.py` for local experiments
- Test files: `test_<module>.py` under mirrored `tests/` tree

**Directories:**
- Package code under `fli/`, `app/`, `fli-js/src/`
- Google Flights models grouped in `*/models/google-flights/` (Python: `google_flights/`)

**Functions:**
- Sync search: `_search_flights_sync`, `_search_dates_sync` in `app/engine.py`
- Async wrappers: `search_flights_async`, `stream_flight_search`
- JS handlers: `handleFlightSearch`, `handleTrackerAdd` (camelCase)
- JS init: `initSavedFlightPresets`, `initTabs`

**API routes:**
- REST prefix `/api/`
- SSE: `GET /api/search/flights`, `GET /api/search/combined`
- Tracker: `/api/tracker/*`, trips: `/api/trips/*`

## Where to Add New Code

**New tracker API endpoint:**
- Route handler: `app/server.py` (group under existing section comments)
- Business logic: `app/engine.py` if search-related; `app/tracker.py` if persistence-related
- Tests: No dedicated `tests/app/` yet — add `tests/app/test_server.py` following `tests/mcp/` patterns

**New flight search filter exposed in tracker UI:**
- Parser/builder (if shared): `fli/core/parsers.py` or `fli/core/builders.py`
- Library search support: `fli/search/flights.py`, `fli/models/google_flights/flights.py`
- Tracker wiring: `app/engine.py::_search_flights_sync` + query param in `app/server.py::search_flights_sse`
- Frontend control: `app/static/index.html` + handler in `app/static/app.js`

**New saved search preset:**
- Hardcoded preset object: `app/static/app.js` near `FIFA_DFW_PRESET` (~1305)
- Register in `initSavedFlightPresets()` — use unique `id`, merge via `localStorage` key `savedFlightPresets`
- Optional `referenceDeals` array for static booking links

**New CLI command:**
- Implementation: `fli/cli/commands/<name>.py`
- Registration: `fli/cli/main.py` (`app.command(...)`)
- Tests: `tests/cli/test_<name>.py`

**New MCP tool:**
- Tool function + params model: `fli/mcp/server.py`
- Tests: `tests/mcp/test_<feature>.py`

**New library search feature (upstream-worthy):**
- Models: `fli/models/google_flights/`
- Search logic: `fli/search/`
- Shared parsing: `fli/core/`
- Mirror in TS: corresponding file under `fli-js/src/`
- Tests: `tests/search/` or `tests/models/`

**New hotel feature:**
- API client changes: `app/hotels.py`
- Engine integration: `app/engine.py::_search_hotels_sync`, `stream_combined_search`
- Route: `app/server.py::search_hotels_endpoint`

**New root trip-planning script:**
- Place at repo root as `find_<purpose>.py` or `plan_<purpose>.py`
- Import `fli` directly: `from fli.search import SearchFlights`
- Do not add to `pyproject.toml` `[project.scripts]` unless promoting to supported tool

**Utilities:**
- Release/version: `scripts/bump_version.py`
- Airport data refresh: `scripts/update_airports.py` → updates `data/airports.csv` and regeneration via `scripts/generate_enums.py`

## Special Directories

**`app/data/`:**
- Purpose: Runtime local data
- Generated: `tracker.db` created on first `TrackerDB()` init
- Committed: `airports_lite.json`, `.gitkeep`; `tracker.db` gitignored

**`tests/search/fixtures/`:**
- Purpose: Binary snapshots of Google API responses for offline decoder tests
- Generated: Via `scripts/capture_fixtures.py`
- Committed: Yes (`.bin` files)

**`public/` and `public_backup_*`:**
- Purpose: Legacy/alternate frontend
- Generated: `public_backup_*` is manual snapshot
- Committed: Present in working tree; separate deploy target from `app/static/`

**`.planning/`:**
- Purpose: GSD milestone/phase docs and codebase maps
- Generated: By GSD commands
- Committed: Yes

**`__pycache__/`, `.venv/`, `.ruff_cache/`, `.pytest_cache/`:**
- Purpose: Local tooling artifacts
- Committed: No

## Module Dependency Rules

Use this order when adding imports to avoid circular dependencies:

```text
fli/models  →  fli/core  →  fli/search  →  fli/cli | fli/mcp
                                    ↓
                              app/engine  →  app/server
                                    ↓
                              app/tracker
```

- `app/tracker.py` may import `app.engine` lazily inside `check_flight_price` to break cycles.
- `app/hotels.py` has no `fli` dependency — keep hotel logic isolated.
- Do not import `app/` from `fli/` (preserves upstream publishability).

## SSE Contract Reference

When extending flight search streaming, match existing events consumed by `app/static/app.js`:

| Event | Source | Client handler |
|-------|--------|----------------|
| `status` | `app/engine.py::stream_flight_search` | `setStatus(message)` |
| `progress` | same | `setStatus(current/total, trip)` |
| `flight_found` | same | Push to `state.flightResults` |
| `complete` | same | Close EventSource, re-enable UI |

Combined search uses `trip_found` instead of `flight_found` (`app/static/app.js` ~728).

---

*Structure analysis: 2026-06-18*
