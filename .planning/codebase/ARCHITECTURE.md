<!-- refreshed: 2026-05-30 -->
# Architecture

**Analysis Date:** 2026-05-30

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Entry Points (4 surfaces)                           │
├─────────────────┬──────────────────┬──────────────────┬───────────────────── ┤
│   CLI (`fli`)   │  MCP STDIO/HTTP  │  Web App (HTTP)  │  Python API (direct) │
│ `fli/cli/main`  │`fli/mcp/server`  │ `app/server.py`  │  `fli/search/*.py`   │
└────────┬────────┴────────┬─────────┴────────┬─────────┴──────────────────────┘
         │                 │                  │
         └────────────────┬┘                  │
                          ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Core Utilities (`fli/core/`)                          │
│  parsers.py  ·  builders.py  ·  airports.py  ·  currency.py                 │
└─────────────────────────────────────────────────────────────────────────────-┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Search Engine (`fli/search/`)                          │
│  SearchFlights  ·  SearchDates  ·  Client (rate-limited HTTP)                │
└──────────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Data Models (`fli/models/`)                           │
│  Airport  ·  Airline  ·  FlightSearchFilters  ·  FlightResult  ·  etc.       │
└──────────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│              Google Flights API (reverse-engineered, no SDK)                  │
│  https://www.google.com/_/FlightsFrontendUi/data/.../GetShoppingResults      │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File(s) |
|-----------|----------------|---------|
| CLI Entry | Smart arg routing; Typer command registration | `fli/cli/main.py` |
| CLI Commands | flights, dates, airports, multi sub-commands | `fli/cli/commands/*.py` |
| CLI Utils | Rich output display, JSON serialization | `fli/cli/utils.py`, `fli/cli/console.py` |
| MCP Server | FastMCP tools (`search_flights`, `search_dates`, `find_airports`), prompts, resources | `fli/mcp/server.py` |
| MCP Entry | Optional-dependency guard wrappers for STDIO/HTTP | `fli/mcp/_entry.py` |
| Core Parsers | Convert string user input to enum/model objects | `fli/core/parsers.py` |
| Core Builders | Construct `FlightSegment` / `TimeRestrictions` objects | `fli/core/builders.py` |
| Core Airports | Fuzzy airport search by name, city, or IATA code | `fli/core/airports.py` |
| Core Currency | Extract and format currency from Google API tokens | `fli/core/currency.py` |
| SearchFlights | POST to Google Flights API, parse raw JSON → `FlightResult` | `fli/search/flights.py` |
| SearchDates | POST to Google Flights date-range API, parse results | `fli/search/dates.py` |
| HTTP Client | curl-cffi session; 10 req/s rate limit; 3-attempt retry | `fli/search/client.py` |
| Data Models | Pydantic models for filters, results, segments, enums | `fli/models/` |
| Web App Server | FastAPI SPA + REST + SSE endpoints for flight/hotel/tracker | `app/server.py` |
| Web App Engine | Async wrappers over `fli` search; thread pool; SSE streaming | `app/engine.py` |
| Web App Tracker | SQLite price-drop monitoring; airline refund policy DB | `app/tracker.py` |
| Web App Airport | Lightweight airport autocomplete for the web UI | `app/airport_data.py` |
| Web App Models | Pydantic request/response models for the web API | `app/models.py` |

## Pattern Overview

**Overall:** Shared-core, multi-surface library. A single `fli/` Python package (models + core + search) is consumed by three distinct surfaces: a Typer CLI, a FastMCP server, and a FastAPI web application.

**Key Characteristics:**
- All surfaces share `fli/core/` parsers and builders — no duplicated parameter logic
- Google Flights API is accessed via direct POST with URL-encoded, reverse-engineered payload (no scraping)
- A singleton HTTP client (`fli/search/client.py`) is shared across surfaces via `get_client()` / module-level globals
- Data validation is enforced via Pydantic v2 throughout the model layer
- Optional dependencies: the `[mcp]` extra isolates FastMCP from core fli dependencies

## Layers

**Presentation Layer (CLI):**
- Purpose: Terminal UX — argument parsing and Rich output
- Location: `fli/cli/`
- Contains: Typer commands, enums (OutputFormat), display helpers
- Depends on: `fli/core/`, `fli/models/`, `fli/search/`
- Used by: Terminal users, shell scripts

**Presentation Layer (MCP):**
- Purpose: AI assistant integration via Model Context Protocol
- Location: `fli/mcp/server.py`
- Contains: FastMCP tools, prompt templates, configuration resource
- Depends on: `fli/core/`, `fli/models/`, `fli/search/`
- Used by: Claude Desktop, Cursor, and other MCP-compatible AI clients

**Presentation Layer (Web App):**
- Purpose: Browser SPA with flight search, hotel search, price tracker
- Location: `app/`
- Contains: FastAPI routes (SSE + REST), async engine wrappers, SQLite tracker
- Depends on: `fli/core/`, `fli/models/`, `fli/search/`, `hot_core` (hotels)
- Used by: Browser clients via `fli-tracker` CLI command

**Core Utilities Layer:**
- Purpose: Parse user string input → domain objects; build filter structures
- Location: `fli/core/`
- Contains: `parsers.py`, `builders.py`, `airports.py`, `currency.py`
- Depends on: `fli/models/` only
- Used by: All three presentation layers

**Search Engine Layer:**
- Purpose: Execute queries against Google Flights API; parse raw responses
- Location: `fli/search/`
- Contains: `SearchFlights`, `SearchDates`, singleton `Client`
- Depends on: `fli/models/`, `curl-cffi`, `ratelimit`, `tenacity`
- Used by: CLI commands, MCP server, web app engine

**Model Layer:**
- Purpose: Type-safe domain model definitions with validation
- Location: `fli/models/`
- Contains: `Airport` enum, `Airline` enum, Pydantic filter and result models
- Depends on: `pydantic` only
- Used by: All other layers

## Data Flow

### Flight Search (all surfaces share this path)

1. **Input parsing** — user string params parsed in `fli/core/parsers.py` (`resolve_airport`, `parse_cabin_class`, `parse_max_stops`, etc.)
2. **Segment building** — `build_flight_segments()` in `fli/core/builders.py` constructs `FlightSegment` objects
3. **Filter assembly** — `FlightSearchFilters` Pydantic model instantiated with segments + filters
4. **API encoding** — `FlightSearchFilters.encode()` in `fli/models/google_flights/flights.py` serializes to URL-encoded JSON
5. **HTTP POST** — `SearchFlights.search()` in `fli/search/flights.py` sends to `GetShoppingResults` endpoint
6. **Response parsing** — raw nested JSON arrays parsed into `FlightResult` / `FlightLeg` models
7. **Multi-leg recursion** — for round-trip/multi-city, `search()` recurses: selects outbound leg, re-queries for return options
8. **Output** — CLI renders with Rich; MCP serializes to dict; web app streams via SSE

### Date Range Search

1. **Input parsing** — same core parsers as flight search
2. **Segment building** — `build_date_search_segments()` in `fli/core/builders.py`
3. **Filter assembly** — `DateSearchFilters` model with `from_date` / `to_date` / `duration`
4. **API call** — `SearchDates.search()` in `fli/search/dates.py`
5. **Results** — list of `(date, price, currency)` records; optionally sorted by price

### Web App Price Tracking

1. User adds a booked flight via `POST /api/tracker/add`
2. `TrackerDB` (SQLite) persists the booking in `app/data/tracker.db`
3. Background asyncio task runs every 6 hours calling `check_all_flights`
4. Each check calls `SearchFlights` for the tracked route; compares against booked price
5. Price drops and history stored back in SQLite; insights returned via `GET /api/tracker/list`

### SSE Streaming (Web App)

1. Browser sends `GET /api/search/flights` with query params
2. FastAPI returns `EventSourceResponse` backed by an async generator
3. `stream_flight_search()` in `app/engine.py` runs blocking search in `ThreadPoolExecutor`
4. Results yielded progressively as `{"event": "result", "data": {...}}` events
5. Client disconnection detected via `await request.is_disconnected()`

**State Management:**
- Module-level singletons: `fli/search/client.py` (`client`), `app/engine.py` (`_flight_search`, `_date_search`, `_executor`)
- Web tracker state: SQLite at `app/data/tracker.db` via `app/tracker.py::TrackerDB`
- MCP config: `FlightSearchConfig` Pydantic settings loaded from `FLI_MCP_*` env vars at import time

## Key Abstractions

**`FlightSearchFilters` (encodes to Google API payload):**
- Purpose: Full parameter set for a flight search — wraps segments, passengers, stops, cabin, sort, bags, emissions
- Location: `fli/models/google_flights/flights.py`
- Pattern: Pydantic model with custom `format()` + `encode()` methods; `encode()` URL-encodes the Google Flights API wire format

**`FlightSegment` (atomic leg of a journey):**
- Purpose: One airport-to-airport leg; holds departure/arrival airports (as nested lists for multi-airport), date, time restrictions, and optionally a `selected_flight` for multi-leg recursion
- Location: `fli/models/google_flights/base.py`
- Pattern: Pydantic model with `@field_validator` and `@model_validator`

**`SearchFlights` (recursive multi-leg fetcher):**
- Purpose: Fetches flight options; for round-trip/multi-city recursively selects legs and re-queries
- Location: `fli/search/flights.py`
- Pattern: Stateless class; uses shared singleton `Client`; returns `list[FlightResult | tuple[FlightResult, ...]]`

**`Client` (singleton rate-limited HTTP session):**
- Purpose: Single shared `curl-cffi` session with 10 req/sec limit and 3-attempt exponential-backoff retry
- Location: `fli/search/client.py`
- Pattern: Module-level singleton via `get_client()`; decorators `@sleep_and_retry`, `@limits`, `@retry` stacked on `get`/`post`

**`Airport` / `Airline` enums:**
- Purpose: Strongly-typed IATA code references; eliminate raw string airport/airline codes throughout
- Location: `fli/models/airport.py`, `fli/models/airline.py`
- Pattern: Python `Enum`; codes starting with a digit prefixed with `_` (e.g., `_3F`)

**`ParseError` (unified input error):**
- Purpose: Single exception type for all user-facing parsing failures; caught at CLI/MCP boundary and formatted as user messages
- Location: `fli/core/parsers.py`
- Pattern: `ParseError(ValueError)` subclass; caught explicitly in CLI commands and MCP tool handlers

## Entry Points

**`fli` CLI:**
- Location: `fli/cli/main.py::cli()`
- Triggers: `fli` console script (pyproject.toml)
- Responsibilities: Smart routing (first non-command arg → `flights` subcommand); delegates to Typer `app()`

**`fli-mcp` (STDIO MCP):**
- Location: `fli/mcp/_entry.py::run()` → `fli/mcp/server.py::run()`
- Triggers: `fli-mcp` console script
- Responsibilities: Guard against missing MCP deps; run FastMCP on stdio transport

**`fli-mcp-http` (HTTP MCP):**
- Location: `fli/mcp/_entry.py::run_http()` → `fli/mcp/server.py::run_http()`
- Triggers: `fli-mcp-http` console script
- Responsibilities: Bind host/port from `HOST`/`PORT` env vars; serve MCP over HTTP at `/mcp/`

**`fli-tracker` (Web App):**
- Location: `app/server.py::main()`
- Triggers: `fli-tracker` console script
- Responsibilities: Open browser, start Uvicorn on `0.0.0.0:8000`; initializes SQLite tracker and background price checker

## Architectural Constraints

- **Threading:** `fli/search/client.py` uses a module-level singleton; the web app's `ThreadPoolExecutor` (8 workers) runs blocking searches off the asyncio event loop via `loop.run_in_executor`
- **Global state:** Module-level singletons in `fli/search/client.py` (`client`), `app/engine.py` (`_flight_search`, `_date_search`, `_executor`), and `app/server.py` (`_tracker_db`, `_bg_task`). All are lazily initialized.
- **Rate limiting:** The `@limits(calls=10, period=1)` decorator on `Client.post()`/`get()` is process-wide; concurrent threads share this limit transparently via `ratelimit`'s thread-safe semaphore.
- **Google API fragility:** `FlightSearchFilters.format()` encodes a reverse-engineered nested array format; many fields are commented `# seemingly no effect`. Changes to Google's API can break parsing silently.
- **Currency:** Google Flights does not expose currency reliably in all responses; a fallback `default_currency` (default `"USD"`) is applied when missing.
- **Multi-city timeout:** `SearchFlights.search()` comment notes distinct-city multi-city searches may time out against the `GetShoppingResults` endpoint; round-trip style multi-city (same origin/destination) is reliable.

## Anti-Patterns

### Hotel module imported via `sys.path` manipulation

**What happens:** `app/engine.py::_get_hotels_core()` adds the project root to `sys.path` at runtime and then does `from hot_core import search_hotels_core`. `hot_core.py` lives in the project root and is not a proper package.
**Why it's wrong:** Brittle path manipulation; `hot_core` is invisible to static analysis and the package build system; breaks if cwd changes.
**Do this instead:** Move `hot_core.py` into `app/` as `app/hotels.py` and import directly as `from app.hotels import search_hotels_core`.

### Module-level singleton for HTTP client

**What happens:** `fli/search/client.py` declares `client = None` at module level; `get_client()` sets it on first call. All surfaces reuse this one instance.
**Why it's wrong:** Shared mutable module state makes testing harder (state leaks between tests); not safe to fork after initialization.
**Do this instead:** Pass the client as a constructor parameter to `SearchFlights`/`SearchDates` or use a context-managed factory; current approach works but requires care in tests.

### `app/server.py` uses `asyncio.get_event_loop()` (deprecated pattern)

**What happens:** `tracker_check_one` and `tracker_check_all` call `asyncio.get_event_loop()` then `loop.run_in_executor(...)`.
**Why it's wrong:** `asyncio.get_event_loop()` is deprecated in Python 3.10+; inside an async handler the correct call is `asyncio.get_running_loop()`.
**Do this instead:** Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in async route handlers.

## Error Handling

**Strategy:** Parse errors surface as `ParseError` (a `ValueError` subclass); all other failures bubble as generic `Exception` with context messages. Both CLI and MCP catch errors at the boundary and convert to user-friendly messages or structured error responses.

**Patterns:**
- `fli/core/parsers.py`: raises `ParseError` with valid-values list for invalid enum/airport/airline input
- `fli/cli/commands/*.py`: catches `ParseError` and `(AttributeError, ValueError)`; outputs Rich text or JSON error depending on `--format`
- `fli/mcp/server.py`: catches `ParseError` and generic `Exception`; returns `{"success": False, "error": "..."}` dict
- `fli/search/flights.py`: catches and re-wraps all exceptions as `Exception("Search failed: ...")`; individual unparseable flight rows are skipped with `logging.debug`

## Cross-Cutting Concerns

**Logging:** Standard library `logging` with `logging.basicConfig(level=logging.INFO)` in `app/server.py`; `logging.debug` in `fli/search/flights.py` for skipped rows. No structured logging framework.
**Validation:** Pydantic v2 on all models; `@field_validator` / `@model_validator` for cross-field constraints (e.g., departure ≠ arrival airport, travel date not in past).
**Authentication:** None — the Google Flights API endpoint is unauthenticated; browser impersonation is achieved via `curl-cffi`'s `impersonate="chrome"` parameter.

---

*Architecture analysis: 2026-05-30*
