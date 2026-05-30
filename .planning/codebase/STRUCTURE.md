# Codebase Structure

**Analysis Date:** 2026-05-30

## Directory Layout

```
Fli-tracker/                       # Project root
├── fli/                           # Core Python library (published to PyPI as "flights")
│   ├── cli/                       # Typer CLI interface
│   │   ├── commands/              # One file per sub-command
│   │   │   ├── airports.py        # `fli airports` command
│   │   │   ├── dates.py           # `fli dates` command
│   │   │   ├── flights.py         # `fli flights` command
│   │   │   └── multi.py           # `fli multi` command (multi-city)
│   │   ├── console.py             # Rich console instance
│   │   ├── enums.py               # CLI-local enums (OutputFormat)
│   │   ├── main.py                # CLI entry point; Typer app + smart routing
│   │   └── utils.py               # Display helpers, JSON serializers, date normalizers
│   ├── core/                      # Shared utilities (parsers + builders)
│   │   ├── airports.py            # Fuzzy airport search (name/city/IATA)
│   │   ├── builders.py            # FlightSegment / TimeRestrictions factory functions
│   │   ├── currency.py            # Price token extraction and formatting
│   │   └── parsers.py             # String → enum conversion; ParseError
│   ├── mcp/                       # MCP server
│   │   ├── _entry.py              # Optional-dep guard wrappers (STDIO + HTTP)
│   │   └── server.py              # FastMCP tools, prompts, resources; config
│   ├── models/                    # Pydantic data models
│   │   ├── airline.py             # Airline enum (IATA codes)
│   │   ├── airport.py             # Airport enum (IATA codes)
│   │   └── google_flights/        # Google Flights specific models
│   │       ├── base.py            # Core models: FlightResult, FlightLeg, FlightSegment,
│   │       │                      #   TimeRestrictions, PassengerInfo, etc.
│   │       ├── dates.py           # DateSearchFilters model
│   │       └── flights.py         # FlightSearchFilters model with encode() / format()
│   └── search/                    # Search engine (API calls)
│       ├── client.py              # Singleton rate-limited curl-cffi HTTP client
│       ├── dates.py               # SearchDates class
│       └── flights.py             # SearchFlights class (recursive multi-leg)
├── app/                           # Web application ("Travel Planner Pro")
│   ├── airport_data.py            # Lightweight airport autocomplete + IATA→city mapping
│   ├── engine.py                  # Async wrappers over fli search; ThreadPoolExecutor; SSE
│   ├── models.py                  # Pydantic request/response models for web API
│   ├── server.py                  # FastAPI app; all REST + SSE routes; lifespan
│   ├── tracker.py                 # SQLite price-drop tracker; airline refund policy DB
│   ├── data/                      # Runtime data files
│   │   ├── airports_lite.json     # Trimmed airport list for web autocomplete
│   │   └── tracker.db             # SQLite database (price tracking history)
│   └── static/                    # Single-page application assets
│       ├── index.html             # SPA entry point
│       ├── app.js                 # Frontend JS (vanilla)
│       └── styles.css             # Stylesheet
├── tests/                         # Test suite (mirrors fli/ structure)
│   ├── cli/                       # CLI command tests
│   ├── core/                      # Core utility tests
│   ├── mcp/                       # MCP server tests
│   ├── models/                    # Model validation tests
│   ├── search/                    # Live API integration tests (may fail due to rate limits)
│   └── conftest.py                # Shared fixtures
├── examples/                      # Standalone usage examples
│   ├── README.md
│   ├── basic_one_way_search.py
│   ├── round_trip_search.py
│   ├── date_range_search.py
│   ├── price_tracking.py
│   └── *.py                       # Additional scenario scripts
├── docs/                          # MkDocs documentation source
│   ├── api/                       # API reference pages
│   ├── guides/                    # How-to guides
│   ├── examples/                  # Example documentation
│   └── index.md
├── scripts/                       # Developer utility scripts
│   ├── generate_enums.py          # Regenerate Airport/Airline enum from CSV data
│   └── update_airports.py         # Update airports.csv from IATA source
├── data/                          # Raw reference data
│   ├── airlines.csv               # Airline IATA data (source for Airline enum)
│   ├── airports.csv               # Airport IATA data (source for Airport enum)
│   └── *.png / *.gif / *.mp4      # Demo assets for README/docs
├── skills/                        # Project-local GSD skills
│   └── fli/
├── pyproject.toml                 # Package config; scripts; ruff; pytest markers
├── pytest.ini                     # Pytest configuration
├── mkdocs.yml                     # MkDocs documentation config
├── docker-compose.yml             # Docker compose for local dev
├── nixpacks.toml                  # Nixpacks deploy config (Railway)
├── railway.toml                   # Railway deployment config
├── hot_core.py                    # Hotel search core (project root — not a package)
├── hotels_mcp.py                  # Hotels MCP server (project root — not a package)
├── flight_gui.py                  # Legacy Tkinter GUI (project root — not a package)
├── plan_trip.py                   # Standalone trip planning script (project root)
├── airports.json                  # Airport data JSON (root-level, redundant with data/)
└── *.json                         # Cached search result snapshots (slc_lgb.json, etc.)
```

## Directory Purposes

**`fli/` (library package):**
- Purpose: The publishable Python library providing flight search capability
- Key files: `fli/cli/main.py` (CLI), `fli/mcp/server.py` (MCP), `fli/search/flights.py` (core search)
- Installed via: `pip install flights` (PyPI package name is `flights`, import name is `fli`)

**`fli/cli/` (CLI layer):**
- Purpose: Typer-based terminal interface
- Contains: One file per command in `commands/`; shared console, utils, and enums
- Key files: `main.py` (entry + smart routing), `utils.py` (output formatting)

**`fli/core/` (shared utilities):**
- Purpose: All parameter parsing and filter building shared between CLI and MCP
- Contains: Stateless pure functions only; no I/O
- Key files: `parsers.py`, `builders.py`

**`fli/mcp/` (MCP server):**
- Purpose: FastMCP-based AI assistant integration
- Contains: `server.py` with tools + prompts + config; `_entry.py` guard wrapper
- Transport: STDIO (Claude Desktop) or HTTP (`/mcp/` path, for Railway/Docker)

**`fli/models/` (data models):**
- Purpose: All Pydantic models and enums used across the library
- Contains: `Airport`/`Airline` enums; Google Flights request/response models
- Key files: `google_flights/base.py` (shared base models), `google_flights/flights.py` (filter + encode)

**`fli/search/` (search engine):**
- Purpose: HTTP communication with Google Flights API
- Contains: `SearchFlights` (specific date search), `SearchDates` (date range), `Client` (transport)
- Key files: `client.py` (singleton with rate limiting + retry), `flights.py` (recursive multi-leg)

**`app/` (web application):**
- Purpose: "Travel Planner Pro" browser SPA with flight search, hotel search, and price tracking
- Contains: FastAPI server, async engine, SQLite tracker, static SPA
- Key files: `server.py` (all routes), `engine.py` (async bridge), `tracker.py` (price monitoring)

**`tests/` (test suite):**
- Purpose: pytest test suite mirroring `fli/` directory structure
- Contains: Unit tests for CLI, core utilities, models, MCP; integration tests for search (live API)
- Note: `tests/search/` hits live Google Flights API; skip with `--ignore=tests/search/` in CI

**`examples/` (usage examples):**
- Purpose: Standalone runnable scripts demonstrating library usage patterns
- Contains: Named scenario files; all ruff-lint checked but docstring rules relaxed

**`scripts/` (developer tools):**
- Purpose: Maintenance scripts for regenerating enum code from CSV source data
- Contains: `generate_enums.py` (Airport/Airline enum codegen), `update_airports.py`

**`data/` (reference data):**
- Purpose: Source CSV data for airport and airline enums; demo media assets
- Contains: `airports.csv`, `airlines.csv` (used by `scripts/` to regenerate enums)

## Key File Locations

**Entry Points:**
- `fli/cli/main.py`: CLI entry point (`cli()` function); registered as `fli` console script
- `fli/mcp/_entry.py`: MCP entry guard; delegates to `fli/mcp/server.py`
- `fli/mcp/server.py`: FastMCP tools, prompts, config, STDIO/HTTP `run()` functions
- `app/server.py`: FastAPI web app; `main()` registered as `fli-tracker` console script

**Core Search Logic:**
- `fli/search/flights.py`: `SearchFlights.search()` — Google Flights API POST + recursive multi-leg
- `fli/search/dates.py`: `SearchDates.search()` — date range price discovery
- `fli/search/client.py`: `Client` + `get_client()` — singleton HTTP transport

**Filter Construction:**
- `fli/models/google_flights/flights.py`: `FlightSearchFilters.format()` + `encode()` — Google API payload serializer
- `fli/models/google_flights/base.py`: `FlightSegment`, `FlightResult`, `FlightLeg`, `TimeRestrictions`
- `fli/core/builders.py`: `build_flight_segments()`, `build_date_search_segments()`, `build_time_restrictions()`

**Parameter Parsing:**
- `fli/core/parsers.py`: `resolve_airport()`, `parse_cabin_class()`, `parse_max_stops()`, `parse_airlines()`, `ParseError`

**Web App:**
- `app/engine.py`: `stream_flight_search()`, `search_flights_async()`, `search_dates_async()` — async bridge
- `app/tracker.py`: `TrackerDB` (SQLite), `check_all_flights()`, `get_refund_eligibility()`

**Configuration:**
- `pyproject.toml`: Package metadata, dependencies, ruff config, pytest markers, console scripts
- `pytest.ini`: Pytest base configuration

**Reference Data (runtime):**
- `app/data/airports_lite.json`: Used by `app/airport_data.py` for web autocomplete
- `app/data/tracker.db`: SQLite price history (created on first run)

## Naming Conventions

**Files:**
- `snake_case.py` for all Python source files
- Test files prefixed `test_` (e.g., `test_flights.py`)
- One command per file in `fli/cli/commands/` matching the command name
- Model files named after the domain object (e.g., `flights.py`, `dates.py`)

**Directories:**
- `snake_case` for all directories
- `__pycache__` auto-generated, not committed
- Test directories mirror source directories (e.g., `tests/cli/` ↔ `fli/cli/`)

**Classes:**
- `PascalCase` (e.g., `SearchFlights`, `FlightSearchFilters`, `TrackerDB`)

**Functions:**
- `snake_case` (e.g., `build_flight_segments`, `resolve_airport`, `parse_cabin_class`)

**Constants / Enums:**
- `UPPER_SNAKE_CASE` for constants (e.g., `BASE_URL`, `BG_CHECK_INTERVAL`)
- Enum members in `UPPER_SNAKE_CASE` (e.g., `SeatType.PREMIUM_ECONOMY`, `TripType.ONE_WAY`)
- Airline/airport codes starting with a digit are prefixed with `_` in the enum (e.g., `Airline._3F`)

## Where to Add New Code

**New CLI sub-command:**
- Create `fli/cli/commands/<command_name>.py` with a function named `<command_name>`
- Register in `fli/cli/main.py` with `app.command(name="<command_name>")(<command_name>)`
- Add corresponding tests in `tests/cli/test_<command_name>.py`
- Use `fli.core` parsers for all parameter parsing; do not duplicate enum resolution logic

**New MCP tool:**
- Add `@mcp.tool()` decorated function in `fli/mcp/server.py`
- Use `Annotated[type, Field(description="...")]` for all parameters
- Follow the existing `_execute_*` helper pattern to separate parameter validation from execution
- Add tests in `tests/mcp/test_mcp_server.py`

**New search filter or model:**
- Add Pydantic model or enum to `fli/models/google_flights/base.py`
- Export from `fli/models/google_flights/__init__.py` and `fli/models/__init__.py`
- Update `FlightSearchFilters.format()` in `fli/models/google_flights/flights.py` to include the new field in the API payload
- Add corresponding parser in `fli/core/parsers.py` if the filter needs string → enum conversion

**New core utility:**
- Add pure function to `fli/core/parsers.py` (string → model) or `fli/core/builders.py` (model factory)
- Export from `fli/core/__init__.py`
- Add tests in `tests/core/`

**New web app endpoint:**
- Add route handler in `app/server.py`
- Add async business logic in `app/engine.py` (keep `server.py` thin)
- Add request/response Pydantic models to `app/models.py`

**New example script:**
- Add to `examples/` with a descriptive filename (e.g., `multi_city_search.py`)
- Follow the existing pattern: import from `fli` directly, no CLI subprocess calls

**New enum data (airports/airlines):**
- Update source CSV in `data/airports.csv` or `data/airlines.csv`
- Run `uv run python scripts/generate_enums.py` to regenerate enum files
- Do not edit `fli/models/airport.py` or `fli/models/airline.py` by hand

## Special Directories

**`.planning/`:**
- Purpose: GSD planning artifacts (roadmap, phase plans, codebase maps)
- Generated: No (managed by GSD workflow tools)
- Committed: Yes

**`.venv/`:**
- Purpose: Virtual environment managed by `uv`
- Generated: Yes
- Committed: No (in `.gitignore`)

**`app/data/`:**
- Purpose: Runtime SQLite database and airport reference JSON
- Generated: `tracker.db` created on first run
- Committed: `airports_lite.json` is committed; `tracker.db` should be gitignored (contains user data)

**`data/` (root):**
- Purpose: Source reference data for enum codegen + demo assets
- Generated: No (maintained manually)
- Committed: Yes

---

*Structure analysis: 2026-05-30*
