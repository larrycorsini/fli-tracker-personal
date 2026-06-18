<!-- refreshed: 2026-06-18 -->
# Architecture

**Analysis Date:** 2026-06-18

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Presentation / Entry Points                          │
├──────────────┬──────────────┬──────────────┬──────────────┬───────────────┤
│  Tracker SPA │  Legacy PWA  │  fli CLI     │  MCP Server  │  Root scripts │
│ app/static/  │   public/    │  fli/cli/    │  fli/mcp/    │  find_*.py    │
│  app.js      │  index.html  │  Typer+Rich  │  FastMCP     │  plan_trip.py │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴───────┬───────┘
       │              │              │              │               │
       ▼              ▼              ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Personal fork — FastAPI tracker (`app/`)                  │
│  `app/server.py`  REST + SSE  │  `app/engine.py`  async wrappers           │
│  `app/tracker.py` SQLite      │  `app/hotels.py`  Google Hotels            │
│  `app/airport_data.py`        │  `app/models.py`  (mostly unused by routes) │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Core library — `fli/` (upstream + shared)                 │
│  `fli/core/` parsers & builders  │  `fli/models/` Pydantic enums & filters  │
│  `fli/search/flights.py`         │  `fli/search/dates.py`                    │
│  `fli/search/client.py`          │  rate-limited curl-cffi HTTP client       │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  External APIs                                                             │
│  Google Flights FlightsFrontendService  │  Google Travel Hotels (Ya3XAc RPC) │
└─────────────────────────────────────────────────────────────────────────────┘

Parallel package (not wired into tracker):
  `fli-js/` — TypeScript port, published independently to npm
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | HTTP routes, SSE streaming, static mount, lifespan background jobs | `app/server.py` |
| Search engine wrapper | Direct `fli` API calls, serialization, batch streaming, thread-pool async | `app/engine.py` |
| Price tracker | SQLite schema, refund policies, price checks, trip planner CRUD | `app/tracker.py` |
| Hotel search | Reverse-engineered Google Hotels batchexecute client | `app/hotels.py` |
| Airport autocomplete | Lite JSON dataset lookup for tracker UI | `app/airport_data.py` |
| Tracker frontend | Tabbed SPA, EventSource SSE client, localStorage presets | `app/static/app.js` |
| CLI | Typer commands: flights, dates, airports, multi | `fli/cli/main.py` |
| MCP server | AI-facing tools: search_flights, search_dates, get_booking_options, find_airports | `fli/mcp/server.py` |
| Flight search | GetShoppingResults / GetBookingResults orchestration | `fli/search/flights.py` |
| HTTP client | Global 10 req/s rate limit, retries, browser impersonation | `fli/search/client.py` |
| Shared parsing | Airport/airline/stop/cabin parsing and filter building | `fli/core/parsers.py`, `fli/core/builders.py` |
| Data models | `FlightSearchFilters`, `FlightResult`, enums | `fli/models/google_flights/` |

## Pattern Overview

**Overall:** Layered library + thin application shell, with multiple entry points converging on the same `fli.search` core.

**Key Characteristics:**
- **Direct API access** — No scraping; protobuf/JSON wire formats to Google Flights and Hotels endpoints.
- **Sync core, async shell** — `SearchFlights.search()` is synchronous; FastAPI uses `ThreadPoolExecutor` and SSE generators in `app/engine.py`.
- **Filter object pattern** — All searches build Pydantic filter models (`FlightSearchFilters`, `DateSearchFilters`) before calling search classes.
- **Serialization boundary** — Tracker app converts `FlightResult` / tuples into flat JSON dicts in `app/engine.py::_serialize_flight`; MCP and CLI have their own formatters.
- **Fork isolation** — Personal features (`app/`, root scripts, `public/`) sit beside upstream-publishable `fli/` and `fli-js/`.

## Layers

**Presentation (tracker SPA):**
- Purpose: User-facing flight/hotel/combined search, price tracking, trip planner
- Location: `app/static/` (`index.html`, `app.js`, `styles.css`)
- Contains: Vanilla JS state machine, EventSource SSE consumer, localStorage prefs
- Depends on: `app/server.py` REST/SSE endpoints
- Used by: Browser at `http://localhost:8000` via `fli-tracker` or `uvicorn app.server:app`

**API / transport:**
- Purpose: Route HTTP, stream SSE, serve static files, schedule background price checks
- Location: `app/server.py`
- Contains: FastAPI routes under `/api/*`, `EventSourceResponse` generators, Pydantic request bodies for tracker/trips
- Depends on: `app/engine.py`, `app/tracker.py`, `app/airport_data.py`
- Used by: `app/static/app.js`, external HTTP clients

**Application services:**
- Purpose: Orchestrate searches, enrich results, persist tracker state
- Location: `app/engine.py`, `app/tracker.py`, `app/hotels.py`
- Contains: Sync search functions, async wrappers, SSE batching, SQLite access, airline refund lookup
- Depends on: `fli.search`, `fli.core`, `fli.models`
- Used by: `app/server.py`, `app/tracker.check_flight_price`

**Domain / search library:**
- Purpose: Google Flights integration shared by CLI, MCP, tracker, and examples
- Location: `fli/`
- Contains: Search orchestrators, decoders (`fli/search/_decoders.py`), wire helpers, enums
- Depends on: `curl-cffi`, `pydantic`, `tenacity`, `ratelimit`
- Used by: All entry points; tests under `tests/`

**TypeScript port:**
- Purpose: npm-publishable JS/TS library mirroring Python `fli/` layout
- Location: `fli-js/src/` (core, models, search)
- Contains: Independent implementation; not imported by Python tracker
- Depends on: `zod`, Bun for tests
- Used by: `examples/typescript/`, npm consumers

## Data Flow

### Primary Request Path — Flight search via SSE

1. **User submits flights form** — `handleFlightSearch` in `app/static/app.js` builds query params, calls `persistRecentSearch`, opens `EventSource` to `/api/search/flights` (`app/static/app.js` ~335–400).

2. **FastAPI SSE endpoint** — `search_flights_sse` in `app/server.py` parses query params (origins, destinations, date range, durations, stops, cabin, airline, trip_type, departure_days), wraps `stream_flight_search` in an async generator, returns `EventSourceResponse` (`app/server.py` ~126–173).

3. **Trip permutation & batching** — `stream_flight_search` in `app/engine.py` expands origin×destination×date×duration×cabin combinations, yields `status`, then processes batches of 8 via `asyncio.gather` (`app/engine.py` ~440–567).

4. **Per-trip search** — Each batch item calls `search_flights_async` → `run_in_executor` → `_search_flights_sync` (`app/engine.py` ~72–160, ~389–405).

5. **Core library call** — `_search_flights_sync` uses `fli.core` parsers/builders to construct `FlightSearchFilters`, then `SearchFlights().search(filters)` (`app/engine.py` ~95–111`; implementation in `fli/search/flights.py`).

6. **HTTP to Google** — `SearchFlights` posts to `FlightsFrontendService/GetShoppingResults` through module-singleton `get_client()` with global 10 req/s token bucket (`fli/search/client.py`).

7. **Serialize & enrich** — Results pass through `_serialize_flight`, optional airline filter, price sort, `TrackerDB.log_search` + historical percentile badges (`app/engine.py` ~116–156, ~176–257).

8. **SSE events back to browser** — Engine yields `flight_found` (with `all_results` array), `progress`, then `complete`. `app.js` listens and pushes into `state.flightResults`, calls `scheduleRenderFlights` (`app/static/app.js` ~403–428).

### Secondary Flow — Price drop check (background)

1. **Lifespan startup** — `app/server.py` creates `_background_price_checker` asyncio task (6-hour interval) (`app/server.py` ~54–81).

2. **Check loop** — `check_all_flights` in `app/tracker.py` loads active tracked flights, calls `check_flight_price` per row (`app/tracker.py` ~709–736).

3. **Re-search** — `check_flight_price` imports `_search_flights_sync` from `app/engine.py`, compares cheapest price, updates SQLite, optionally fires macOS `osascript` notification (`app/tracker.py` ~656–706).

### Secondary Flow — Combined flight + hotel SSE

1. `handleCombinedSearch` in `app/static/app.js` opens `/api/search/combined`.
2. `stream_combined_search` in `app/engine.py` runs `_search_flights_sync` then `_search_hotels_sync` per trip (sequential, not batched).
3. Hotels call `search_hotels_core` in `app/hotels.py` (Google Travel `Ya3XAc` RPC).

### Saved search presets (client-only)

1. `initSavedFlightPresets` on DOM load merges hardcoded `FIFA_DFW_PRESET` into `localStorage.savedFlightPresets` (`app/static/app.js` ~1305–1350).
2. `renderRecentSearches` renders chip buttons from `savedFlightPresets` and `recentSearches` keys (`app/static/app.js` ~1396–1423).
3. Chip click → `applyFlightSearch` fills form fields and `renderReferenceDeals` (booking deep links) (`app/static/app.js` ~1459–1479).

**State Management:**
- **Server:** Module-level singletons — `_tracker_db`, `_flight_search`, `_date_search`, `_executor` in `app/server.py` / `app/engine.py`.
- **Client:** `state` object in `app/static/app.js`; persistence via `localStorage` (`tpp-prefs`, `savedFlightPresets`, `recentSearches`).
- **Database:** SQLite WAL at `app/data/tracker.db` — tracked flights, price history, search history, trips.

## Key Abstractions

**FlightSearchFilters / DateSearchFilters:**
- Purpose: Canonical input to all flight/date searches
- Examples: Built in `app/engine.py`, `fli/cli/commands/flights.py`, `fli/mcp/server.py`
- Pattern: Pydantic models in `fli/models/google_flights/`; segments built via `fli/core/builders.py`

**SearchFlights / SearchDates:**
- Purpose: Stateful search orchestrators wrapping Google API endpoints
- Examples: `fli/search/flights.py`, `fli/search/dates.py`
- Pattern: Class with `.search(filters)`; `SearchFlights` caches session id for `get_booking_options` (not thread-safe per docstring)

**TrackerDB:**
- Purpose: All tracker persistence and trip planner data
- Examples: `app/tracker.py`
- Pattern: Raw `sqlite3` with `row_factory`, schema in `_init_db`, no ORM

**SSE event envelope:**
- Purpose: Streaming progress to browser
- Examples: `{"event": "flight_found"|"progress"|"status"|"complete", "data": {...}}` from `app/engine.py`
- Pattern: Server yields dicts; `EventSourceResponse` JSON-encodes `data` field

## Entry Points

**Tracker web app:**
- Location: `app/server.py` (`main()` via `fli-tracker` script in `pyproject.toml`)
- Triggers: `uv run fli-tracker`, `uv run uvicorn app.server:app --reload`
- Responsibilities: Full personal fork UI + API on port 8000

**CLI (`fli`):**
- Location: `fli/cli/main.py` → `fli/cli/commands/*.py`
- Triggers: `uv run fli flights JFK LAX 2026-05-15`; bare args default to `flights` subcommand
- Responsibilities: Terminal flight/date search with Rich output

**MCP STDIO / HTTP:**
- Location: `fli/mcp/_entry.py` → `fli/mcp/server.py`
- Triggers: `fli-mcp`, `fli-mcp-http` (`pyproject.toml` scripts)
- Responsibilities: AI assistant tools with industry-standard parameter names

**Root trip-planning scripts:**
- Location: `find_*.py`, `plan_trip.py`, `scratch_*.py`, `generate_flight_report.py`, etc.
- Triggers: Manual `uv run python <script>.py`
- Responsibilities: Ad-hoc route research; import `fli` directly or subprocess CLI; not part of packaged wheel surface beyond `app/` + `fli/`

**Legacy static PWA:**
- Location: `public/index.html`, `public/heatmap.html`, `public/history.html`
- Triggers: Static hosting (e.g. Netlify per `.netlify/`)
- Responsibilities: Separate curated-flight PWA; not served by `app/server.py` (which mounts `app/static/`)

## Architectural Constraints

- **Threading:** `SearchFlights` is not thread-safe; `app/engine.py` uses a shared singleton with `ThreadPoolExecutor(max_workers=8)` — concurrent searches can race on session cache. Prefer per-request instances for booking flows (`fli/search/flights.py` docstring).
- **Rate limiting:** Global 10 req/s across all threads via `TokenBucketRateLimiter` in `fli/search/client.py`. Tracker batches of 8 parallel searches must stay under this ceiling.
- **Global state:** `_flight_search`, `_date_search`, `_executor` in `app/engine.py`; `_tracker_db` in `app/server.py`; `get_client()` singleton in `fli/search/client.py`.
- **Async boundary:** FastAPI routes are `async def` but Google API calls run in thread pool — no native async HTTP in search path.
- **Price nullability:** Upstream can return `FlightResult` with `price=None`; `_serialize_flight` returns `None` and engine skips unpriced rows when sorting.
- **Package boundary:** `pyproject.toml` wheel includes `fli` and `app` only; root scripts and `public/` are local-only.

## Anti-Patterns

### Shared SearchFlights singleton under concurrent load

**What happens:** `app/engine.py` lazily creates one `SearchFlights()` reused across all tracker searches and price checks.

**Why it's wrong:** `SearchFlights` documents session-id races when multiple `.search()` calls overlap; booking token cache can cross-pollinate.

**Do this instead:** Instantiate `SearchFlights()` per request for booking flows; for high-concurrency tracker batches consider per-batch instances or explicit `session_id` passing per `fli/search/flights.py` guidance.

### New TrackerDB per search log

**What happens:** `_search_flights_sync` constructs `TrackerDB()` on every successful search to log cheapest price (`app/engine.py` ~132–141).

**Why it's wrong:** Extra SQLite connections and bypasses server singleton `_get_db()`.

**Do this instead:** Accept injected `TrackerDB` from `app/server.py` or use a module-level shared instance.

### Duplicate frontends (`app/static` vs `public`)

**What happens:** Two independent UIs exist — FastAPI-served tracker SPA and Netlify-oriented `public/` PWA.

**Why it's wrong:** Feature drift, duplicated flight-display logic, unclear canonical UI.

**Do this instead:** Treat `app/static/` as the active tracker UI; migrate or deprecate `public/` explicitly when consolidating.

## Error Handling

**Strategy:** Fail soft at application boundary; log warnings; return empty lists or partial SSE streams rather than 500s for search failures.

**Patterns:**
- `app/engine.py` sync functions wrap in `try/except`, log `logger.warning`, return `[]`.
- SSE generator catches per-trip errors in `fetch_trip`, continues batch (`app/engine.py` ~525–527).
- `fli/search/exceptions.py` defines typed HTTP/timeout/connection errors for library consumers.
- Tracker API returns `JSONResponse` with `success: false` and HTTP status codes for validation errors (`app/server.py`).

## Cross-Cutting Concerns

**Logging:** `logging.getLogger("server"|"engine"|"tracker")` with `INFO` default in `app/server.py`.

**Validation:** Query params parsed manually in routes; Pydantic `BaseModel` for POST bodies (`AddFlightRequest`, `TripCreateRequest`). Library uses Pydantic filter models.

**Authentication:** None — local single-user tracker; no auth middleware on FastAPI routes.

---

*Architecture analysis: 2026-06-18*
