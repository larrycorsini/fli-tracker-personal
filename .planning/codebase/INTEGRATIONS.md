# External Integrations

**Analysis Date:** 2026-05-30

## APIs & External Services

**Google Flights (Reverse-Engineered API):**
- Service: Google Flights
  - What it's used for: Core flight search (prices, schedules, airline data) and cheapest-date scanning
  - SDK/Client: `curl-cffi` with browser TLS impersonation (`fli/search/client.py`)
  - Endpoint: `https://www.google.com/_/TravelFrontendUi/data/batchexecute` (POST, `rpcids` for flights)
  - Auth: None — impersonated browser session (no API key required)
  - Rate limit: 10 req/sec enforced via `ratelimit` + `tenacity` retries (`fli/search/client.py`)
  - Note: No official API contract; relies on reverse-engineered payload format in `fli/search/`

**Google Hotels (Reverse-Engineered API):**
- Service: Google Hotels / Travel
  - What it's used for: Hotel search by city and check-in/checkout dates (`app/server.py` → `search_hotels_async`)
  - SDK/Client: `httpx` with standard browser User-Agent spoofing (`hot_core.py`)
  - Endpoint: `https://www.google.com/_/TravelFrontendUi/data/batchexecute?rpcids=Ya3XAc`
  - Auth: None — standard HTTP POST with browser headers
  - Note: Response parsing is structural (positional JSON array traversal in `hot_core.py:traverse_and_extract`); fragile to Google response format changes

**MCP Protocol (AI Assistant Integration):**
- Service: MCP (Model Context Protocol) — any compatible AI client (Claude, etc.)
  - What it's used for: Exposing `search_flights`, `search_dates`, `find_airports` tools to AI assistants
  - SDK/Client: `fastmcp` >=3.2.0 (`fli/mcp/server.py`)
  - Transports: STDIO (`fli-mcp`) and HTTP streaming (`fli-mcp-http`, port 8000, path `/mcp/`)
  - Auth: None (caller's responsibility)
  - Required header for HTTP: `Accept: application/json, text/event-stream`

## Data Storage

**Databases:**
- SQLite (local file)
  - Purpose: Price drop tracker — stores tracked flights, price history, search history, trip plans
  - Location: `app/data/tracker.db` (created at runtime, see `app/tracker.py:DB_PATH`)
  - Client: Python stdlib `sqlite3` with WAL journal mode
  - Schema: `tracked_flights`, `price_history`, `search_history`, `trips`, `trip_items` tables
  - Migration: Inline `ALTER TABLE` with `OperationalError` catch for idempotent column adds

**File Storage:**
- Local filesystem only
  - `app/data/` — SQLite database
  - `app/static/` — Frontend SPA files (`index.html`, `styles.css`, `app.js`)
  - `airports.json` — Airport data reference file in project root

**Caching:**
- In-process only
  - `app/engine.py` uses `functools.lru_cache` for airport resolution
  - Shared singleton instances: `_flight_search: SearchFlights`, `_date_search: SearchDates`, `_executor: ThreadPoolExecutor(max_workers=8)` in `app/engine.py`
  - MCP server creates fresh `SearchFlights()` / `SearchDates()` per request (no persistent cache)

## Authentication & Identity

**Auth Provider:**
- None — no user authentication in any component
  - The library, MCP server, and tracker web app have no login/session/auth system
  - All API endpoints are open (local-use app assumption)

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or similar integration

**Logs:**
- Python stdlib `logging` module throughout
  - `app/server.py`: `logger = logging.getLogger("server")`, level INFO
  - `app/engine.py`: `logger = logging.getLogger("engine")`, warnings on search failures
  - `app/tracker.py`: `logger = logging.getLogger("tracker")`
  - Log level set via `logging.basicConfig(level=logging.INFO)` in `app/server.py`

**Analytics:**
- Google Analytics (documentation site only)
  - Configured in `mkdocs.yml` via `GOOGLE_ANALYTICS_KEY` env var
  - Applies only to the MkDocs documentation site, not the application

## CI/CD & Deployment

**Hosting:**
- Railway (production MCP server)
  - Builder: NIXPACKS (`railway.toml`, `nixpacks.toml`)
  - Start: `fli-mcp-http` on port 8000
  - Config: `railway.toml` (1 replica, sleep on idle, restart on failure)
- Docker / GHCR (`ghcr.io/punitarani/fli:latest`)
  - Multi-stage `python:3.12-slim` image (`Dockerfile`)
  - Published on push to `main` and on GitHub releases
  - `docker-compose.yml` for local container deployment

**CI Pipeline:**
- GitHub Actions (`.github/workflows/`)
  - `test.yml` — lint + Railway build validation + pytest matrix (Python 3.10–3.13)
  - `lint.yml` — ruff format + check
  - `docker.yml` — build and push to GHCR on `main` push and releases (amd64 + arm64)
  - `docs.yml` — MkDocs build and deploy to GitHub Pages on `main` push
  - `publish.yml` — PyPI publish on GitHub release (via OIDC trusted publishing to `pypi` environment)

**Package Registry:**
- PyPI: package name `flights` (version 0.8.5)
  - Published via `pypa/gh-action-pypi-publish` with OIDC (no stored API token)

## Environment Configuration

**Required env vars (runtime):**
- `HOST` — bind address for HTTP server (default `0.0.0.0`)
- `PORT` — bind port for HTTP server (default `8000`)

**Optional MCP server env vars (all prefixed `FLI_MCP_`):**
- `FLI_MCP_DEFAULT_PASSENGERS` — default passenger count (default `1`)
- `FLI_MCP_DEFAULT_CURRENCY` — fallback currency code (default `USD`)
- `FLI_MCP_DEFAULT_CABIN_CLASS` — default cabin class (default `ECONOMY`)
- `FLI_MCP_DEFAULT_SORT_BY` — default sort strategy (default `CHEAPEST`)
- `FLI_MCP_DEFAULT_DEPARTURE_WINDOW` — default departure window in `HH-HH` format (optional)
- `FLI_MCP_MAX_RESULTS` — max results per tool call (optional, unlimited if unset)

**CI/CD secrets:**
- `GITHUB_TOKEN` — auto-provided by GitHub Actions for GHCR login and PyPI OIDC
- `GOOGLE_ANALYTICS_KEY` — used only in MkDocs docs build for analytics

**Secrets location:**
- GitHub Actions repository secrets and OIDC environments (no secrets in codebase)
- No `.env` file committed or required for basic operation

## Webhooks & Callbacks

**Incoming:**
- None — no webhook endpoints in any component

**Outgoing:**
- None — no outbound webhooks; all external API calls are synchronous request/response

## Notifications

**macOS system notifications:**
- `app/tracker.py` uses `subprocess.run(["osascript", "-e", ...])` to send a macOS desktop notification when a tracked flight's price drops
- Platform-specific: silently fails on non-macOS systems (exception caught and logged)

---

*Integration audit: 2026-05-30*
