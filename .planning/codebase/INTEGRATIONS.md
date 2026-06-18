# External Integrations

**Analysis Date:** 2026-06-18

## APIs & External Services

**Google Flights (reverse-engineered internal API):**
- Primary integration for all flight search, date search, and booking options
- Endpoints (Python: `fli/search/flights.py`, `fli/search/dates.py`; TS: `fli-js/src/search/flights.ts`, `fli-js/src/search/dates.ts`):
  - `GetShoppingResults` — flight itinerary search
  - `GetBookingResults` — per-vendor booking fares
  - `GetCalendarGraph` — cheapest-date calendar
- Base host: `https://www.google.com/_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/...`
- Public booking/deep links: `https://www.google.com/travel/flights` (`fli/core/links.py`, `fli-js/src/core/links.ts`)
- SDK/Client: `curl-cffi` with browser impersonation (Python, `fli/search/client.py`); native `fetch` with browser-like headers (TS, `fli-js/src/search/client.ts`)
- Auth: **None** — unauthenticated public API calls; rate-limited to 10 req/sec globally
- Locale params: `curr`, `hl`, `gl` URL parameters (`fli/search/_urls.py`)

**Google Travel Hotels (reverse-engineered):**
- Hotel search in tracker combined search flow
- Endpoint: `https://www.google.com/_/TravelFrontendUi/data/batchexecute?rpcids=Ya3XAc...` (`app/hotels.py`)
- SDK/Client: `httpx.Client` (stdlib sync POST)
- Auth: **None** — mimics browser User-Agent only
- Called via `app/engine.py` → `search_hotels_async` → `search_hotels_core`

**Airline manage-booking URLs (static reference data):**
- Hardcoded policy + manage URLs in `app/tracker.py` `AIRLINE_POLICIES` (AA, DL, UA, WN, etc.)
- Used for refund-eligibility badges and links in tracker UI; no live API calls

## Data Storage

**Databases:**
- **SQLite** — local tracker persistence
  - File: `app/data/tracker.db` (gitignored; schema init in `app/tracker.py` `TrackerDB._init_db`)
  - Tables: tracked flights, price history, trips/items (via `app/server.py` trip endpoints)
  - Client: stdlib `sqlite3` with WAL mode (`PRAGMA journal_mode=WAL`)
  - Connection: file path `app/data/tracker.db` (no env var)

**File Storage:**
- **Local filesystem** — primary storage model
  - `app/data/airports_lite.json` — airport autocomplete (`app/airport_data.py`)
  - `data/airports.csv`, `data/airlines.csv` — enum source for `fli-js` code generation (`fli-js/scripts/generate-enums.ts`)
  - `app/static/` — tracker SPA assets served by FastAPI
  - `public/` — generated static reports (`index.html`, `history.html`, `heatmap.html`) deployed to Netlify
  - `tests/search/fixtures/*.bin` — recorded Google API responses for offline tests
  - Root-level `*.json` scratch/output files from local search scripts (untracked)

**Caching:**
- **Service Worker** — offline cache for static `public/` PWA (`public/sw.js`)
- **In-memory** — `@lru_cache` and module singletons in `app/engine.py` (`SearchFlights`, `SearchDates`, thread pool)
- **No Redis/external cache**

## Authentication & Identity

**Auth Provider:**
- **None** for tracker API, MCP server, or CLI
- FastAPI endpoints in `app/server.py` are unauthenticated (open CORS-style local tool)
- MCP HTTP server (`fli/mcp/server.py`) has no auth middleware
- Google API calls require no API keys

**MCP configuration (not auth):**
- `FlightSearchConfig` via `pydantic-settings` with `FLI_MCP_` env prefix (`fli/mcp/server.py`)
- Defaults: passengers, currency, cabin class, sort, max results

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- Python `logging` module — `app/server.py`, `app/engine.py`, `app/tracker.py`, `fli/search/`
- Uvicorn access/error logs when running tracker or MCP HTTP
- CI publishes JUnit XML via `EnricoMi/publish-unit-test-result-action` (`.github/workflows/ci.yml`)

## CI/CD & Deployment

**Hosting:**
| Target | What runs | Config |
|--------|-----------|--------|
| Railway | `fli-mcp-http` MCP server | `railway.toml`, `nixpacks.toml` |
| GHCR | Docker MCP image | `Dockerfile`, `.github/workflows/docker.yml` |
| GitHub Pages | MkDocs documentation | `.github/workflows/docs.yml` |
| PyPI | `flights` Python package | `.github/workflows/release.yml` |
| npm | `fli-js` package | `.github/workflows/release-npm.yml` |
| Netlify | Static `public/` reports | `daily_flight_search.sh` (`netlify-cli deploy --prod --dir=public`) |
| Local | FastAPI tracker on :8000 | `uv run fli-tracker` / `app/server.py` |

**CI Pipeline:**
- GitHub Actions (`.github/workflows/ci.yml`) — ruff, pytest (3.10–3.13), fli-js lint/test, Railway/Nixpacks smoke, actionlint
- `act` supported locally (`make ci`)

## Environment Configuration

**Required env vars:**
- **None strictly required** for core operation
- Optional:
  - `FLI_TIMEOUT` — request timeout override
  - `HOST`, `PORT` — MCP HTTP bind (Railway sets `PORT`)
  - `FLI_MCP_DEFAULT_PASSENGERS`, `FLI_MCP_DEFAULT_CURRENCY`, etc. — MCP defaults
  - `HTTPS_PROXY` / `HTTP_PROXY` — `fli-js` proxy routing
  - `GOOGLE_ANALYTICS_KEY` — docs site only

**Secrets location:**
- No committed secrets detected
- PyPI Trusted Publishing via GitHub Actions (`.github/workflows/publish.yml`)
- npm publish uses `NPM_TOKEN` secret (`.github/workflows/publish-npm.yml`)
- GHCR uses `GITHUB_TOKEN` (`.github/workflows/docker.yml`)

## Webhooks & Callbacks

**Incoming:**
- None — no webhook receivers; tracker uses REST + SSE only (`app/server.py`)

**Outgoing:**
- **Google Flights/Hotels APIs** — outbound HTTP only (search, booking, hotels)
- **Apple iMessage** — local `osascript` to Messages.app (`alert.py`); not a network webhook
- **Netlify CLI** — deploy push from `daily_flight_search.sh` (requires local Netlify auth token in user's Netlify config, not in repo)

## Tracker API Surface (integration boundary)

FastAPI routes in `app/server.py` expose the local integration layer:

| Route | Backend integration |
|-------|---------------------|
| `GET /api/search/flights` | SSE stream → `app/engine.py` → `fli.search.SearchFlights` → Google |
| `GET /api/search/dates` | `SearchDates` → Google calendar API |
| `GET /api/search/hotels` | `app/hotels.py` → Google Travel batchexecute |
| `GET /api/search/combined` | Flights + hotels parallel via `stream_combined_search` |
| `GET /api/airports` | Local `app/data/airports_lite.json` |
| `POST /api/tracker/*` | SQLite `app/tracker.py` + live price re-check via `fli` |
| `GET /api/rates` | Hardcoded static rates in `app/server.py` (not a live FX API) |

## MCP Tools (AI assistant integration)

MCP server (`fli/mcp/server.py`) exposes tools that wrap the same Google Flights stack:

- `search_flights`, `search_dates`, `get_booking_options`, `find_airports`
- Transport: STDIO (`fli-mcp`) or HTTP streamable (`fli-mcp-http`, default `0.0.0.0:8000`)
- No external MCP auth; relies on network access to Google

## Exchange Rates

- **Not a live integration** — `EXCHANGE_RATES` dict is hardcoded in `app/server.py` (`/api/rates`)
- Used for UI currency display only

## Test vs Production External Calls

- `tests/search/` and some MCP tests hit **live Google APIs** (rate-limited, flaky in CI)
- CI ignores `tests/search/` and skips `test_search_dates_round_trip` (`.github/workflows/ci.yml`, `Makefile` `test` target)
- `fli-js` E2E tests require `FLI_E2E=1` (`fli-js/tests/e2e/live_search.test.ts`)
- Stubbed fixtures used for reliable unit/integration tests (`tests/search/fixtures/`, `fli-js/tests/integration/`)

---

*Integration audit: 2026-06-18*
