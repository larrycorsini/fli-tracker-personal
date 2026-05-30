# Codebase Concerns

**Analysis Date:** 2026-05-30

---

## Tech Debt

### Root-Level Personal Script Sprawl

- Issue: Five scripts live at the repo root with no package structure: `track_my_flight.py`, `flight_gui.py`, `plan_trip.py`, `hot_core.py`, `hotels_mcp.py`, `test_hotels.py`. They were authored as one-off personal tools and never integrated into the proper package.
- Files: `track_my_flight.py`, `flight_gui.py`, `plan_trip.py`, `hot_core.py`, `hotels_mcp.py`, `test_hotels.py`
- Impact: Creates ambiguity about what the project actually is. Pollutes the package namespace. `hot_core.py` is now imported by `app/engine.py` via a `sys.path` hack because it lives at root.
- Fix approach: Move `hot_core.py` into `app/` (it's the hotel search core used by the app), archive or delete `flight_gui.py` (superseded by `app/server.py`), delete `test_hotels.py` (one-liner smoke test), move `track_my_flight.py` and `plan_trip.py` into `examples/` or `scripts/`.

### Hardcoded Personal Absolute Paths in Scripts

- Issue: Three root-level scripts hardcode the developer's home directory path as the uv binary location.
- Files: `track_my_flight.py:33`, `flight_gui.py:795`, `flight_gui.py:874`, `plan_trip.py:12`
- Impact: Scripts fail immediately on any machine other than the original author's. Breaks CI if these are ever run there.
- Fix approach: Replace `"/Users/larry/.local/bin/uv"` with `shutil.which("uv")` or just `"uv"` and rely on `PATH`.

### `flight_gui.py` Superseded But Not Removed

- Issue: `flight_gui.py` is an older copy of the web GUI that uses Python's built-in `BaseHTTPRequestHandler`. It spawns `fli` as subprocesses and is functionally replaced by `app/server.py` (FastAPI + direct Python API).
- Files: `flight_gui.py`
- Impact: Dual server on port 8000 — running both simultaneously causes a port conflict. Maintains duplicate logic including the hotel search integration.
- Fix approach: Delete `flight_gui.py`; direct users to `app/server.py` / `fli-tracker` CLI.

### `hot_core.py` Imported via `sys.path` Hack

- Issue: `app/engine.py` imports `hot_core` via a `sys.path.insert(0, root)` mutation at runtime to reach the project root.
- Files: `app/engine.py:39-50`
- Impact: Fragile import that breaks if working directory changes. Not discoverable by linters, type checkers, or package tools.
- Fix approach: Move `hot_core.py` to `app/hotels.py` and import it directly as `from app.hotels import search_hotels_core`.

### `airports.json` (9 MB) Committed to Repo Root

- Issue: A 9 MB raw airports JSON dataset lives at the repo root as a versioned file.
- Files: `airports.json`
- Impact: Bloats git history on every update. Slows clone times. The `app/` module has its own curated `app/data/airports_lite.json` (158 KB) that's better suited.
- Fix approach: Add `airports.json` to `.gitignore` and generate/download it via a `scripts/update_airports.py` call.

### `tracker.db` SQLite File Committed to Version Control

- Issue: `app/data/tracker.db` is a binary SQLite database tracked by git.
- Files: `app/data/tracker.db`
- Impact: User-generated data (tracked flights, price history) gets committed. The file will corrupt git diffs on every write. Merges across branches will conflict.
- Fix approach: Add `*.db` to `.gitignore`. The `app/data/.gitkeep` already exists to preserve the directory.

### `asyncio.get_event_loop()` Deprecated Usage

- Issue: Six call sites use `asyncio.get_event_loop()` inside running async functions, which is deprecated since Python 3.10 and raises `DeprecationWarning` in 3.12.
- Files: `app/server.py:61`, `app/server.py:333`, `app/server.py:344`, `app/engine.py:399`, `app/engine.py:418`, `app/engine.py:429`
- Impact: Will emit warnings in Python 3.12 and may become a runtime error in future Python versions.
- Fix approach: Replace `loop = asyncio.get_event_loop(); await loop.run_in_executor(...)` with `await asyncio.get_running_loop().run_in_executor(...)` or simply `await asyncio.to_thread(sync_fn, *args)`.

### `fuzz` Pytest Marker Not Registered

- Issue: `tests/search/test_search_flights_fuzz.py` uses `@pytest.mark.fuzz` but only the `parallel` marker is registered in `pyproject.toml`'s `[tool.pytest.ini_options]`.
- Files: `pyproject.toml`, `tests/search/test_search_flights_fuzz.py`
- Impact: Running `pytest` emits `PytestUnknownMarkWarning` for fuzz tests, which is noise and can fail strict CI configurations.
- Fix approach: Add `"fuzz: marks fuzz tests (deselect with '-m not fuzz')"` to the `markers` list in `pyproject.toml`.

### Hardcoded Static Exchange Rates

- Issue: `app/server.py` exposes `/api/rates` with hardcoded exchange rates (EUR, GBP, CAD, etc.) that are never updated.
- Files: `app/server.py:444-456`
- Impact: Currency conversion values drift silently from reality. No indication to the UI that rates are stale.
- Fix approach: Either fetch rates from a free API (e.g., `open.er-api.com`) with a 24-hour cache, or document the static rates prominently and add a `rates_updated_at` timestamp to the response.

### Playwright Dependency Never Used

- Issue: `playwright>=1.58.0` is listed as a core dependency in `pyproject.toml` but is not imported anywhere in the codebase (`fli/`, `app/`, `tests/`).
- Files: `pyproject.toml:35`
- Impact: Adds ~100 MB to installs (including browser binaries). Slows `uv sync` significantly.
- Fix approach: Remove `playwright` from core dependencies. If browser automation is anticipated, add it as an optional extra.

---

## Known Bugs

### Commented-Out Round-Trip Tests (Live API Timeouts)

- Symptoms: Four round-trip search tests are disabled via comment block because they cause frequent CI timeouts.
- Files: `tests/search/test_search_flights.py:185-193`
- Trigger: Round-trip search requires multiple sequential API requests (outbound + return per result), hitting the Google Flights rate limit on slow CI runners (HTTP 429).
- Workaround: Tests are commented out. The `TODO` comment states they should be refactored to mock the HTTP client.

### `TrackerDB` Instance Created Per Search Call

- Symptoms: Every call to `_search_flights_sync` creates a new `TrackerDB()` instance (and thus a new SQLite connection) to log historical price data.
- Files: `app/engine.py:138`
- Trigger: Any flight search via the app server.
- Impact: Opens and closes SQLite connections on every search; under concurrent load (the thread pool has 8 workers) this multiplies SQLite write contention.
- Fix approach: Pass the shared `_get_db()` instance from `app/server.py` into the engine functions, or use `app/engine.py`'s own module-level singleton.

---

## Security Considerations

### `osascript` Notification Injection Risk

- Risk: `app/tracker.py` constructs a macOS `osascript` command using an f-string that embeds flight data directly — including user-supplied origin/destination codes and airline names.
- Files: `app/tracker.py:688-690`
- Current mitigation: None. The string is passed directly as `-e` to `osascript`.
- Recommendations: Sanitize the `msg` string to escape double quotes and backslashes before embedding in the AppleScript string. Alternatively use `osascript -e 'display notification (system attribute "MSG") with title "..."'` with environment variable injection to avoid string interpolation in the shell command entirely.

### No CORS Policy on FastAPI Server

- Risk: `app/server.py` does not configure `fastapi.middleware.cors.CORSMiddleware`, meaning any origin can make requests to the API.
- Files: `app/server.py`
- Current mitigation: Server binds to `0.0.0.0:8000` which is already local-only in typical home setups.
- Recommendations: If the server is intended for local use only, add `CORSMiddleware` allowing only `http://localhost:8000`. If it may be exposed externally, this is a higher-priority issue.

### No Authentication on Tracker API

- Risk: All `/api/tracker/*` endpoints (add flight, view booked prices, delete flights) are publicly accessible with no authentication layer.
- Files: `app/server.py:302-364`
- Current mitigation: Local-only deployment makes external access unlikely.
- Recommendations: For any non-local deployment, add a simple API key check or session-based authentication middleware.

---

## Performance Bottlenecks

### `hot_core.py` Full-Response String Parsing

- Problem: The hotel search function splits the entire Google Hotels API response on `"\n"` and calls `json.loads()` on every line, including length-prefix lines it then skips. The `traverse_and_extract` function recursively walks the entire nested JSON tree.
- Files: `hot_core.py:59-73`
- Cause: Defensive parsing of an undocumented API format; the recursive traversal has no depth limit and visits every node.
- Improvement path: Add a maximum recursion depth guard. Pre-filter chunks before attempting `json.loads` using a fast startswith check for `"["` or `"{"`.

### Thread Pool + Rate-Limited Singleton Client

- Problem: `app/engine.py` runs up to 8 concurrent flight searches in a `ThreadPoolExecutor`, but `fli/search/client.py`'s `get_client()` returns a module-level singleton. The `@limits(calls=10, period=1)` decorator from `ratelimit` uses a shared counter across threads; concurrent calls will block each other waiting for the rate limiter, reducing effective parallelism.
- Files: `app/engine.py:58`, `fli/search/client.py:86-96`
- Cause: Singleton HTTP client shared across threaded workers plus a global rate limiter.
- Improvement path: The 10 req/sec limit is per the client instance; with 8 workers this is effectively ~1.25 req/s per worker. Consider per-worker client instances or tuning the pool size to match the rate limit.

---

## Fragile Areas

### `hot_core.py` Positional Index Parsing

- Files: `hot_core.py:10-14`
- Why fragile: Hotel data is extracted by accessing array indices directly (`v[5]`, `v[7][0][0]`, `v[8][0]`, `v[13][0]`) from an undocumented reverse-engineered Google Hotels API response. Any change to the API response structure silently returns wrong data (wrong names, missing prices, wrong ratings) with no error raised.
- Safe modification: Add length and type assertions before each index access. Add an integration smoke test that checks returned hotel objects have non-empty `name`, numeric `price_val`, and a valid `rating`.
- Test coverage: Zero — `hot_core.py` has no tests at all.

### `fli/search/flights.py` Response Parsing

- Files: `fli/search/flights.py`
- Why fragile: Flight data is parsed from a reverse-engineered undocumented Google Flights API. Field positions (legs, price, duration, stops) are accessed by magic indices derived from observed API responses. The `except (IndexError, TypeError)` clauses silently skip malformed data.
- Safe modification: When adding new parsed fields, always guard with `try/except (IndexError, TypeError, KeyError)` matching existing patterns. Any Google-side API change will cause silent empty results rather than errors.
- Test coverage: Price parsing is unit-tested (`TestParsePriceInfo`), but the full response parsing path relies on live API calls.

### `app/tracker.py` SQLite Migrations

- Files: `app/tracker.py:252-316`
- Why fragile: Schema migrations are implemented as `try/except` blocks around `ALTER TABLE` statements. Adding `trip_items` table and `order_index` column at lines 308-312 is done at startup without versioning.
- Safe modification: Any new column additions must use `ALTER TABLE ... ADD COLUMN` in the same `try/except` pattern. Destructive changes (renaming or removing columns) are not safe with this migration approach.
- Test coverage: No tests for `TrackerDB` class at all.

---

## Scaling Limits

### Google Flights API Rate Limit (HTTP 429)

- Current capacity: 10 requests/second per client instance (enforced client-side).
- Limit: Google will return HTTP 429 when too many requests are made from a single IP/session. The existing `@retry` with 3 attempts handles transient 429s but not sustained rate limiting.
- Scaling path: The rate limit is per-IP. Running multiple concurrent app instances behind a load balancer would require per-instance clients or a distributed rate limiter. The current design assumes a single server process.

### SQLite as Price History Store

- Current capacity: Adequate for single-user / small household use (hundreds of tracked flights).
- Limit: SQLite WAL mode supports concurrent reads but serializes writes. Under the async server with background price checks + concurrent manual checks, write contention will increase.
- Scaling path: For multi-user or hosted deployment, migrate `TrackerDB` to PostgreSQL via SQLAlchemy.

---

## Dependencies at Risk

### `curl-cffi` Browser Impersonation

- Risk: The `curl-cffi` library impersonates specific Chrome browser versions to avoid bot detection. Google Flights periodically updates fingerprint detection. A Google-side update could break all searches.
- Impact: Complete failure of `SearchFlights` and `SearchDates`.
- Migration plan: Monitor `curl-cffi` release notes for TLS fingerprint updates. The version constraint `>=0.7.4` is loose enough to auto-update.

### Reverse-Engineered API Stability

- Risk: Both the Google Flights integration (`fli/search/`) and the Google Hotels integration (`hot_core.py`) rely on undocumented internal APIs. Neither has any official support contract.
- Impact: Any silent API structure change returns empty or incorrect results with no user-visible error.
- Migration plan: Add integration smoke tests that run on a schedule (e.g., daily CI) and alert on empty results or parsing failures. Consider caching the last known-good response format.

---

## Missing Critical Features

### No Tests for `app/` Module

- Problem: `app/server.py`, `app/engine.py`, `app/tracker.py`, `app/airport_data.py`, and `app/models.py` have zero test coverage. This is the majority of the application logic.
- Blocks: Confident refactoring of engine, tracker, or server code.

### No Input Validation on Date Parameters

- Problem: Date string parameters (`departure_date`, `start_date`, `end_date`, `return_date`) are accepted as raw strings throughout `app/server.py` routes and passed directly to `fli`'s search functions. Malformed dates are only caught at the point of parsing inside `_search_flights_sync` or `_search_dates_sync`, returning empty results with no error message to the caller.
- Files: `app/server.py:126-168`, `app/server.py:172-220`
- Blocks: Meaningful error messages to the UI when users enter invalid dates.

---

## Test Coverage Gaps

### `app/` Module — Zero Coverage

- What's not tested: `app/engine.py` (flight/date/hotel search orchestration, streaming, serialization), `app/tracker.py` (TrackerDB CRUD, price check logic, airline policies), `app/server.py` (all API routes), `app/airport_data.py`
- Files: Entire `app/` directory
- Risk: Regressions in the price tracker, search engine, or API routes are undetected until manual use.
- Priority: High

### `hot_core.py` — Zero Coverage

- What's not tested: `search_hotels_core()`, `traverse_and_extract()`
- Files: `hot_core.py`
- Risk: Silent failures on Google Hotels API structure changes go unnoticed.
- Priority: High

### Round-Trip Search — Disabled

- What's not tested: Round-trip search with outbound + return selection, round-trip result structure validation
- Files: `tests/search/test_search_flights.py:185-193` (commented out)
- Risk: Round-trip search regressions are not caught by automated tests.
- Priority: Medium

### `fli/core/currency.py` — Minimal Coverage

- What's not tested: Currency extraction from live token format, edge cases in currency parsing
- Files: `fli/core/currency.py`
- Risk: Currency display bugs in non-USD results.
- Priority: Low

---

*Concerns audit: 2026-05-30*
