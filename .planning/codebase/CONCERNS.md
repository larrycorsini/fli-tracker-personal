# Codebase Concerns

**Analysis Date:** 2026-06-18

## Tech Debt

**Hotel module migration (CLEAN-01 partial):**
- Issue: `hot_core.py` removed and logic lives in `app/hotels.py`, but vestiges remain — `app/engine.py` docstring still says "hot_core", and `AGENTS.md` still references the old `sys.path` hack. Root scratch scripts (`scratch.py`) use hardcoded absolute `sys.path.append(...)`.
- Files: `app/hotels.py`, `app/engine.py`, `scratch.py`, `AGENTS.md`
- Impact: Confusing onboarding; scratch scripts break on other machines; import path inconsistency across ad-hoc tooling.
- Fix approach: Finish CLEAN-01 per `.planning/REQUIREMENTS.md` — update docstrings/docs, remove or relocate scratch scripts under `examples/` or `scripts/` with package-relative imports.

**Legacy `flight_gui.py` (CLEAN-02 pending):**
- Issue: 932-line standalone `HTTPServer` + embedded HTML duplicates functionality now in `app/server.py` (FastAPI + SSE). Still imports `app.hotels.search_hotels_core` and loads `airports.json` from repo root (not `app/data/`).
- Files: `flight_gui.py`
- Impact: Two divergent UIs to maintain; broken airport lookup if `airports.json` missing at cwd; no price-tracker integration.
- Fix approach: Archive to `examples/archive/flight_gui.py` with README note, or delete after verifying no references (CLEAN-02).

**Generic Google Flights URLs instead of per-itinerary `booking_url` (FEAT-01/02/03 pending):**
- Issue: `app/engine.py` `_serialize_flight()` never calls `SearchFlights.build_flight_booking_url()`. SSE and combined search use `_build_google_flights_url()` — a route/date search-page link, not the deterministic `tfs` deep link available in `fli/search/flights.py` and used by CLI/MCP.
- Files: `app/engine.py` (`_serialize_flight`, `_build_google_flights_url`, `stream_flight_search`), `app/static/app.js` (renders `f.url`), `fli/cli/commands/flights.py`, `fli/mcp/server.py` (reference implementation)
- Impact: "Book Flight" links open generic search results, not the specific itinerary; violates user preference for clickable buy links; v1.1 milestone blocked.
- Fix approach: After serialization, call `_get_flight_search().build_flight_booking_url(flight, currency=...)` and attach `booking_url` to each result dict; propagate through SSE `flight_found` events and date search responses; update UI to prefer `booking_url` over `url`.

**Dual frontend directories (`public/` vs `app/static/`):**
- Issue: FastAPI serves `app/static/index.html` + `app/static/app.js` at `/`. A separate `public/` tree exists (638-line `index.html`, PWA `manifest.json`, `sw.js`, `heatmap.html`, `history.html`) plus `public_backup_20260618_104813/` — neither wired into `app/server.py`.
- Files: `app/server.py`, `app/static/`, `public/`, `public_backup_20260618_104813/`
- Impact: UI changes may land in the wrong tree; PWA assets unused by the running app; backup folder adds repo noise.
- Fix approach: Pick one canonical frontend (`app/static/` for v1.1), merge any `public/` features needed, delete or gitignore backups.

**Root-level script sprawl:**
- Issue: ~32 Python files at repo root (`find_*.py`, `scratch_*.py`, `update_find_direct.py`, `generate_flight_report.py`, etc.) plus dozens of untracked JSON output files. These are personal trip-planning artifacts, not part of the packaged library or tracker app.
- Files: `find_direct.py`, `find_cheapest.py`, `scratch_search.py`, `daily_flight_search.sh`, `*.json` at root, etc.
- Impact: Clutters git status; unclear what is maintained vs ephemeral; risk of accidental commits of search output or local DB paths.
- Fix approach: Move retained scripts to `scripts/` or `examples/` (CLEAN-04 deferred); add output patterns to `.gitignore`; document in README which entry points matter (`fli`, `fli-tracker`, `fli-mcp`).

**Deployment config targets MCP, not tracker:**
- Issue: `nixpacks.toml` `[start]` runs `fli-mcp-http`; `docker-compose.yml` only defines `fli-mcp` service. Tracker entry point `fli-tracker = "app.server:main"` in `pyproject.toml` has no container/deploy recipe in-repo.
- Files: `nixpacks.toml`, `docker-compose.yml`, `pyproject.toml`
- Impact: Deploying via Nixpacks/Docker runs MCP server, not the price-tracker web app.
- Fix approach: Add tracker service to `docker-compose.yml` or separate `Dockerfile`/Nixpacks profile for `uv run fli-tracker` / `uvicorn app.server:app`.

**Hardcoded demo booking URLs in frontend:**
- Issue: `app/static/app.js` contains hardcoded `tfs` booking URLs (around lines 1323–1335) for sample/demo routes.
- Files: `app/static/app.js`
- Impact: Stale links if shown to users; confuses real API-driven booking flow.
- Fix approach: Remove demo URLs once FEAT-03 wires API `booking_url`; use empty state or docs examples instead.

**Engine docstring / comment drift:**
- Issue: `_search_hotels_sync` docstring references "hot_core"; `_get_hotels_core` lazy-import exists though `app.hotels` is now a proper package module.
- Files: `app/engine.py`
- Impact: Minor confusion during v1.1 cleanup.
- Fix approach: Simplify to direct `from app.hotels import search_hotels_core` and update comments.

## Known Bugs

**`tracker.db` not actually gitignored:**
- Symptoms: `app/data/tracker.db` appears as modified in git status despite docs stating it is gitignored.
- Files: `.gitignore` (line 167: `# *.db` is commented out), `app/data/tracker.db`, `AGENTS.md`, `.planning/PROJECT.md`
- Trigger: Any local tracker usage modifies the DB file; git tracks it.
- Workaround: Manually avoid staging; uncomment `*.db` or add `app/data/tracker.db` to `.gitignore`.
- Fix approach: Uncomment `*.db` or add explicit `app/data/tracker.db`; ensure empty DB schema is created on first run (already in `TrackerDB._init_db()`).

**Price percentile logic treats missing price as `$0`:**
- Symptoms: When assigning `price_level` badges, code uses `f.get("price", 0)` — unpriced rows (already filtered in sort) could skew percentiles if any slip through.
- Files: `app/engine.py` (lines 144–151)
- Trigger: Upstream returns priced + unpriced mix; edge case in percentile assignment.
- Workaround: Null-price flights are mostly filtered in `_serialize_flight`.
- Fix approach: Use explicit `if p is None: continue` in percentile loop (TEST-02 regression target).

**Airline filter uses substring match on display name:**
- Symptoms: `airline_filter` checks `airline_filter.lower() not in airline_name` — "AA" won't match "American Airlines"; "spirit" might false-positive.
- Files: `app/engine.py` (lines 122–125)
- Trigger: User sets airline filter via API query param `airline=`.
- Workaround: Filter client-side in UI.
- Fix approach: Match on IATA code field or use `parse_airlines()` like CLI/MCP.

**`stream_combined_search` blocks the async event loop:**
- Symptoms: Combined flight+hotel SSE handler calls synchronous `_search_flights_sync` and `_search_hotels_sync` directly inside an `async def` generator instead of `run_in_executor`.
- Files: `app/engine.py` (`stream_combined_search`, lines 606–622)
- Trigger: `/api/search/combined` with many date permutations.
- Workaround: Use flight-only SSE endpoint which uses async wrappers.
- Fix approach: Use `search_flights_async` / `search_hotels_async` or `run_in_executor` consistently.

**Circular import between tracker and engine:**
- Symptoms: `app/tracker.py` imports `_search_flights_sync` from `app.engine` inside `check_flight_price()`; `app/engine.py` imports `TrackerDB` at module level.
- Files: `app/tracker.py`, `app/engine.py`
- Trigger: Import order changes or new top-level imports could cause `ImportError`.
- Workaround: Lazy import in tracker already mitigates runtime cycle.
- Fix approach: Extract shared search facade or move price-check orchestration to a third module (e.g. `app/services/price_check.py`).

## Security Considerations

**No authentication on tracker API:**
- Risk: Any client with network access can add/list/delete tracked flights and read confirmation codes via REST (`/api/tracker/*`).
- Files: `app/server.py` (tracker routes ~306–470)
- Current mitigation: None — intended as local/personal tool.
- Recommendations: Bind to `127.0.0.1` in dev; add optional API key or basic auth for LAN deployment; never expose confirmation codes in list responses if not needed by UI.

**Unrestricted search proxy:**
- Risk: `/api/search/flights`, `/api/search/combined`, `/api/search/hotels` proxy to Google with no auth, enabling abuse as an open relay (rate limits apply via `fli` client but are per-process).
- Files: `app/server.py`, `app/engine.py`, `fli/search/client.py`
- Current mitigation: Built-in 10 req/s rate limit in `fli/search/client.py`.
- Recommendations: Add request throttling middleware on FastAPI; cap concurrent SSE connections; require auth if deployed publicly.

**Confirmation codes stored in SQLite plaintext:**
- Risk: `tracked_flights.confirmation_code` stored unencrypted; DB file readable on disk.
- Files: `app/tracker.py` (schema), `app/server.py` (`AddFlightRequest`)
- Current mitigation: Local-only deployment assumption.
- Recommendations: Treat DB as sensitive; ensure gitignore; optional field-level encryption if syncing.

**Hotel search hits Google internal RPC without browser impersonation hardening:**
- Risk: `app/hotels.py` uses raw `httpx` POST to `/_/TravelFrontendUi/data/batchexecute` — may break or trigger blocking; no retry/rate-limit parity with flight client.
- Files: `app/hotels.py`
- Current mitigation: Personal-use volume only.
- Recommendations: Align with `curl-cffi` impersonation pattern from `fli/search/client.py`; mock in tests (TEST-03).

## Performance Bottlenecks

**SSE flight scan combinatorial explosion:**
- Problem: `stream_flight_search()` generates every origin × destination × date × duration × cabin permutation; large ranges produce hundreds/thousands of API calls batched at 8.
- Files: `app/engine.py` (`stream_flight_search`, `BATCH_SIZE = 8`)
- Cause: Exhaustive grid search with no early termination or caching.
- Improvement path: Date-range caps, user-configurable max combos, result caching in SQLite, or calendar pre-filter via `SearchDates`.

**New `TrackerDB()` per flight search for logging:**
- Problem: `_search_flights_sync()` instantiates `TrackerDB()` on every successful search to log cheapest price and compute percentiles — opens new SQLite connection each time under thread pool load.
- Files: `app/engine.py` (line 132), `app/tracker.py` (`_get_conn`)
- Cause: No shared DB handle in engine layer.
- Improvement path: Inject shared `TrackerDB` from server singleton or pass optional db param; reuse connection with thread-local or WAL-safe pooling.

**Background price checker runs sequentially:**
- Problem: `check_all_flights()` loops tracked flights one-by-one with live Google searches every 6 hours.
- Files: `app/server.py` (`_background_price_checker`), `app/tracker.py` (`check_all_flights`)
- Cause: No batching or parallelism for tracker re-checks.
- Improvement path: Batch with `asyncio.gather` + executor; respect rate limits; skip unchanged routes.

**Hotel parsing scans entire JSON tree:**
- Problem: `traverse_and_extract()` recursively walks all nested structures with magic index heuristics (`v[5]`, `v[8]`, etc.).
- Files: `app/hotels.py`
- Cause: Reverse-engineered response format without schema.
- Improvement path: Target known response paths; cache city/date results briefly.

## Fragile Areas

**Google Hotels response parsing:**
- Files: `app/hotels.py` (`traverse_and_extract`, `search_hotels_core`)
- Why fragile: Depends on undocumented array indices in Google TravelFrontendUi batchexecute responses; silent `except Exception: continue` swallows parse failures; empty list indistinguishable from error.
- Safe modification: Capture fixture responses in `tests/fixtures/`; add structural validation before index access; log parse failures at WARNING.
- Test coverage: No tests under `tests/` — only ad-hoc `test_hotels.py` at repo root calling live API.

**Flight serialization for tuple/multi-city results:**
- Files: `app/engine.py` (`_serialize_flight`)
- Why fragile: Branches for round-trip tuple, multi-city tuple, and one-way; price taken from `flight[-1].price` for multi-city; broad try/except returns `None`.
- Safe modification: Add unit tests per trip type (TEST-02); mirror MCP `serialize_flight_result` logic from `fli/mcp/server.py`.
- Test coverage: None in `tests/app/`; library tests don't cover app serialization.

**Live Google Flights API tests:**
- Files: `tests/search/test_search_flights.py`, `tests/search/test_search_dates.py`, `tests/search/test_search_flights_new_filters_live.py`, `tests/mcp/test_mcp_server.py`
- Why fragile: Hit real API; frequent HTTP 429/timeouts on CI; round-trip tests commented out with TODO (lines 185–193 in `test_search_flights.py`).
- Safe modification: Run with `--ignore=tests/search/` locally/CI; refactor commented tests to use wire fixtures like `tests/search/test_booking_url.py`.
- Test coverage: Stubbed tests exist for wire/decoders; live tests remain for integration signal only.

**macOS-only price-drop notifications:**
- Files: `app/tracker.py` (`check_flight_price`, `osascript` subprocess)
- Why fragile: `display notification` fails on Linux/CI/Docker; caught and logged only.
- Safe modification: Gate on `sys.platform == "darwin"` or use optional push notification abstraction.
- Test coverage: None.

## Scaling Limits

**SQLite single-file storage:**
- Current capacity: One writer at a time (WAL mode enabled); fine for personal tracker (dozens of flights, thousands of price_history rows).
- Limit: Concurrent SSE searches + background checker + manual CRUD may see `database is locked` under heavy parallel load.
- Scaling path: Move to PostgreSQL if multi-user; or serialize DB writes through a queue.

**ThreadPoolExecutor (8 workers) + at most one process:**
- Current capacity: 8 parallel flight searches per tracker process; aligns with ~10 req/s fli client limit.
- Limit: Multiple uvicorn workers would duplicate executors and multiply API pressure.
- Scaling path: Single worker for tracker deployment; external job queue for batch scans.

**In-memory exchange rates:**
- Files: `app/server.py` (`EXCHANGE_RATES`, `/api/rates`)
- Limit: Static rates drift from market; no refresh mechanism.
- Scaling path: Optional external rates API or remove if unused.

## Dependencies at Risk

**Reverse-engineered Google APIs (flights + hotels):**
- Risk: Undocumented endpoints; response shape changes break parsers silently.
- Impact: Empty search results, wrong prices, or HTTP blocks.
- Migration plan: Monitor upstream `fli` fixes; add fixture-based regression tests; hotels module should follow flight client's impersonation/retry patterns.

**`curl-cffi` browser impersonation:**
- Risk: Google may block impersonated fingerprints; tied to flight search reliability.
- Impact: All flight/date search paths fail.
- Migration plan: Upstream `fli` maintenance; tracker inherits fixes via dependency bump.

## Missing Critical Features

**App test suite (TEST-01 through TEST-04):**
- Problem: No `tests/app/` directory; FastAPI routes, engine serialization, and hotel wrapper untested in CI.
- Blocks: Safe v1.1 ship; regression detection for null-price filtering, booking URLs, tracker CRUD.
- Files: Missing `tests/app/`; `.planning/REQUIREMENTS.md` defines scope.

**Per-itinerary booking links in API/UI (FEAT-01/02/03):**
- Problem: Documented v1.1 requirement; CLI and MCP already expose `booking_url`.
- Blocks: User workflow for one-click booking from tracker UI.

**Booking options in tracker (FEAT-05 deferred):**
- Problem: No `get_booking_options` integration in `app/server.py` or UI.
- Blocks: Vendor fare comparison from tracker.

## Test Coverage Gaps

**FastAPI endpoints — untested:**
- What's not tested: `/`, `/api/airports`, `/api/search/*` SSE, `/api/tracker/*` CRUD, background lifespan, `/api/rates`.
- Files: `app/server.py`
- Risk: Route regressions, SSE disconnect handling, validation errors ship unnoticed.
- Priority: High (TEST-01)

**Engine serialization — untested:**
- What's not tested: `_serialize_flight` null-price filtering, round-trip tuple shape, `price_level` badges, `_build_google_flights_url`, future `booking_url` attachment.
- Files: `app/engine.py`
- Risk: v1.0 merge regression (null prices crashing sort) could recur.
- Priority: High (TEST-02)

**Hotel search wrapper — untested with mocks:**
- What's not tested: `search_hotels_core`, engine hotel URL builder, deduplication/sort.
- Files: `app/hotels.py`, `app/engine.py` (`_search_hotels_sync`)
- Risk: Google response format change returns empty hotels silently.
- Priority: Medium (TEST-03)

**Tracker DB operations — untested:**
- What's not tested: `TrackerDB` CRUD, `expire_departed_flights`, percentile math, `check_flight_price` integration.
- Files: `app/tracker.py`
- Risk: Price drop detection or savings calculation bugs.
- Priority: Medium

**Live API tests in default CI:**
- What's not tested reliably: `tests/search/*` live tests, `tests/mcp/test_mcp_server.py` (`test_search_dates_round_trip` noted flaky in `AGENTS.md`).
- Files: `tests/search/`, `tests/mcp/test_mcp_server.py`
- Risk: CI noise masks real failures; developers skip full test runs.
- Priority: Medium — document `uv run pytest -vv --ignore=tests/search/`; convert to fixtures.

**Ad-hoc root test scripts — not in pytest:**
- What's not tested: `test_hotels.py`, `test_heatmap.py` live at repo root, not discovered as part of standard `make test`.
- Files: `test_hotels.py`, `test_hotels.py` imports `hotels_mcp`
- Risk: False confidence if run manually only.
- Priority: Low

---

*Concerns audit: 2026-06-18*
