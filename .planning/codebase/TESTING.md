# Testing Patterns

**Analysis Date:** 2026-06-18

## Test Framework

**Runner:**
- **pytest** `>=8.3.4` (dev dependency in `pyproject.toml`)
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`
- Root conftest: `tests/conftest.py` (custom CLI options and collection hooks)

**Assertion Library:**
- Plain `assert` statements (no separate assertion library)

**Plugins:**
- `pytest-asyncio>=0.25.2` — async MCP HTTP tests (`@pytest.mark.asyncio`)
- `pytest-xdist>=3.6.1` — parallel marker support (`@pytest.mark.parallel` on fuzz tests)
- `pytest-cov>=6.0.0` — installed but **not used** in `make test` or Python CI job

**Custom markers** (`pyproject.toml`):
```python
"parallel: marks tests that can run in parallel"
"fuzz: marks fuzz tests (deselect with '-m not fuzz')"
```

**Custom CLI options** (`tests/conftest.py`):
- `--fuzz` — run fuzz tests only (or include fuzz when combined with collection logic)
- `--mcp` — filter collection to MCP tests only (`"mcp" in item.nodeid`)
- `--all` — run full suite including fuzz; skips fuzz-gating in `pytest_runtest_setup`

**Run Commands:**
```bash
make test              # Standard: uv run pytest -vv --ignore=tests/search/
make test-mcp          # MCP only: uv run pytest -vv --mcp
make test-fuzz         # Fuzz only: uv run pytest -vv --fuzz
make test-all          # Everything: uv run pytest -vv --all

# Direct equivalents
uv run pytest -vv --ignore=tests/search/          # Local default (AGENTS.md)
uv run pytest -vv tests/ --all -v \
  --ignore=tests/search/ \
  -k "not test_search_dates_round_trip"           # CI command (.github/workflows/ci.yml)
```

## Test File Organization

**Location:**
- All tests live under `tests/` — **separate from source**, not co-located.
- Directory structure **mirrors `fli/`**:
  - `tests/cli/` → `fli/cli/`
  - `tests/core/` → `fli/core/`
  - `tests/models/` → `fli/models/`
  - `tests/search/` → `fli/search/`
  - `tests/mcp/` → `fli/mcp/`
  - `tests/scripts/` → `scripts/`
- **`tests/app/` does not exist** — v1.1 goal per `.planning/REQUIREMENTS.md` (`TEST-01`, `TEST-02`).

**Naming:**
- Files: `test_<module_or_feature>.py`
- Package `__init__.py` present in `tests/cli/`, `tests/mcp/`, `tests/scripts/` (empty or minimal)

**Structure:**
```
tests/
├── conftest.py                 # Global pytest options and fuzz gating
├── cli/
│   ├── conftest.py             # Shared CLI mocks (SearchFlights, SearchDates, console)
│   ├── test_flights.py
│   ├── test_dates.py
│   ├── test_errors.py
│   └── ...
├── core/
│   ├── test_parsers.py
│   ├── test_builders.py
│   └── ...
├── models/
│   ├── test_flight_search_filters.py
│   └── ...
├── search/
│   ├── fixtures/               # Captured .bin API responses (offline snapshots)
│   ├── test_client.py
│   ├── test_decoders.py
│   ├── test_search_flights.py  # LIVE API — flaky
│   ├── test_search_flights_fuzz.py
│   ├── test_snapshot_fixtures.py
│   └── ...
├── mcp/
│   ├── test_mcp_server.py      # Integration (some live API)
│   ├── test_mcp_server_unit.py # Private helper unit tests
│   ├── test_mcp_http.py        # HTTP transport boot tests
│   └── ...
└── scripts/
    └── test_bump_version.py
```

## Test Structure

**Suite Organization:**

*Function-based (most common):*
```python
def test_basic_flights_search(runner, mock_search_flights, mock_console):
    """Test basic flight search with required parameters."""
    result = runner.invoke(app, ["flights", "JFK", "LAX", date])
    assert result.exit_code == 0
    mock_search_flights.search.assert_called_once()
```

*Class-based (grouped unit tests):*
```python
class TestWrapRequestError:
    """_wrap_request_error must map curl_cffi errors to typed SearchClientError subclasses."""

    def test_timeout_exc_returns_search_timeout_error(self):
        ...
```

*Table-driven / parametrize:*
```python
@pytest.mark.parametrize(
    "exc, expected_type",
    [
        (SearchTimeoutError("timed out"), "timeout"),
        (SearchConnectionError("dns"), "connection_error"),
        ...
    ],
)
def test_json_error_payload_maps_error_types(exc, expected_type):
    ...
```

**Patterns:**
- **Setup:** `@pytest.fixture` functions; shared fixtures in `tests/cli/conftest.py`.
- **Teardown:** `yield` fixtures for reset (e.g. `_reset_client_singleton` in `tests/search/test_client.py` restores module singleton).
- **Autouse fixtures:** isolate side effects (`_isolated_tmp_log_dir` in `tests/cli/test_errors.py`).
- **Assertion:** direct `assert`; mock call verification via `.assert_called_once()` on `MagicMock`.

## Mocking

**Framework:** `unittest.mock` (`MagicMock`, `patch` patterns) + pytest `monkeypatch`.

**Patterns:**

*Monkeypatch class construction (CLI tests):*
```python
@pytest.fixture
def mock_search_flights(monkeypatch):
    mock = MagicMock()
    mock.search.return_value = [FlightResult(...)]
    monkeypatch.setattr("fli.search.flights.SearchFlights.__new__", lambda cls: mock)
    monkeypatch.setattr("fli.search.SearchFlights.__new__", lambda cls: mock)
    return mock
```
Source: `tests/cli/conftest.py`

*MagicMock for domain objects (MCP unit tests):*
```python
def _make_leg(self, **overrides):
    leg = MagicMock()
    leg.departure_airport = "JFK"
    ...
    return leg
```
Source: `tests/mcp/test_mcp_server_unit.py`

*Singleton reset (client tests):*
```python
@pytest.fixture(autouse=True)
def _reset_client_singleton():
    original = client_module.client
    client_module.client = None
    yield
    client_module.client = original
```
Source: `tests/search/test_client.py`

*Console output suppression:*
```python
@pytest.fixture
def mock_console(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("fli.cli.utils.console", mock)
    return mock
```
Source: `tests/cli/conftest.py`

**What to Mock:**
- `SearchFlights` / `SearchDates` in CLI tests — avoid live API.
- Rich `console` in CLI tests — suppress terminal output.
- `curl_cffi` exception classes in client unit tests — test error mapping without network.
- Private MCP serializers' inputs as `MagicMock` legs/airlines.
- Filesystem paths (`_LOG_DIR`) and subprocess/git operations in script tests.

**What NOT to Mock:**
- Pydantic model construction in model validation tests — use real `FlightSearchFilters`, `FlightSegment`, etc.
- Decoder/parser logic under test — feed real fixture bytes from `tests/search/fixtures/`.
- Enum resolution in `fli/core/parsers.py` tests — exercise real `resolve_enum` / `parse_airlines`.

## Fixtures and Factories

**Test Data:**

*Inline model factories in fixtures:*
```python
@pytest.fixture
def basic_search_params():
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    return FlightSearchFilters(
        passenger_info=PassengerInfo(adults=1, ...),
        flight_segments=[FlightSegment(...)],
        ...
    )
```
Source: `tests/search/test_search_flights.py`

*Captured API snapshots:*
- Binary fixtures in `tests/search/fixtures/*.bin`
- Regenerated via `uv run python scripts/capture_fixtures.py`
- Consumed by `tests/search/test_snapshot_fixtures.py` (offline parser regression)

*Dynamic date helpers:*
```python
def get_future_date(days: int = 30) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
```
Used across `tests/models/`, `tests/mcp/`, `tests/cli/`.

**Location:**
- Shared CLI mocks: `tests/cli/conftest.py`
- Search snapshot binaries: `tests/search/fixtures/`
- Module-scoped fixtures for expensive setup: `@pytest.fixture(scope="module")` in `tests/search/test_snapshot_fixtures.py`

## Coverage

**Requirements:** No enforced Python coverage threshold in CI or Makefile.

**pytest-cov:** Listed in dev dependencies but not wired into `make test` or `.github/workflows/ci.yml` Python job.

**View Coverage (manual, if needed):**
```bash
uv run pytest tests/ --ignore=tests/search/ --cov=fli --cov-report=term-missing
```

**fli-js (separate):** Bun test coverage in CI (`bun run test:ci`) — not part of Python test scope.

**Known gaps:**
- **`app/` has zero tests** — planned `tests/app/` for FastAPI routes, engine wrappers, tracker CRUD (v1.1 / `TEST-01`, `TEST-02`).
- Live search integration tests excluded from default runs.
- `test_search_dates_round_trip` excluded in CI (`-k "not test_search_dates_round_trip"`).

## Test Types

**Unit Tests:**
- Scope: parsers, builders, decoders, wire/proto helpers, model validation, client error mapping, MCP serializers.
- Location: `tests/core/`, `tests/models/`, `tests/search/test_decoders.py`, `tests/search/test_client.py`, `tests/mcp/test_mcp_server_unit.py`, `tests/scripts/`.
- No network; fast and reliable.

**Integration Tests (offline):**
- Snapshot replay: `tests/search/test_snapshot_fixtures.py` — feeds captured `.bin` responses through parser.
- Booking URL / proto round-trips: `tests/search/test_booking_url.py`, `tests/search/test_proto.py`.

**Integration Tests (live API):**
- Location: `tests/search/` (especially `test_search_flights.py`, `test_search_dates.py`, `test_search_flights_new_filters_live.py`, `test_mcp/test_mcp_server.py`).
- Hit real Google Flights API — **flaky** (HTTP 429 rate limits, empty results, stale routes).
- **Excluded from `make test`** via `--ignore=tests/search/`.
- Retry pattern for live searches:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def search_with_retry(search, search_params):
    results = search.search(search_params)
    if not results:
        raise ValueError("Empty results, retrying...")
    return results
```
Source: `tests/search/test_search_flights.py`

**Fuzz Tests:**
- File: `tests/search/test_search_flights_fuzz.py`
- Marked `@pytest.mark.fuzz` and `@pytest.mark.parallel`
- Gated behind `--fuzz` or `--all`; removed from normal collection in `pytest_collection_modifyitems`
- Uses seeded random cases (`random.seed(42)`) against live API

**CLI Tests:**
- Framework: `typer.testing.CliRunner`
- Pattern: `runner.invoke(app, ["flights", "JFK", "LAX", date])` with `mock_search_flights`
- Files: `tests/cli/test_*.py`

**MCP Tests:**
- Unit: `tests/mcp/test_mcp_server_unit.py` — private helpers, no server boot.
- Integration: `tests/mcp/test_mcp_server.py` — calls `_search_flights_from_params` (live API when successful).
- HTTP transport: `tests/mcp/test_mcp_http.py` — boots uvicorn in background thread, `@pytest.mark.asyncio` client tests.

**E2E Tests:**
- Not used for Python tracker app or CLI.
- MCP HTTP tests are the closest end-to-end Python coverage.

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_lists_tools_over_http(http_mcp_url):
    async with Client(http_mcp_url) as client:
        tools = await client.list_tools()
        ...
```
Source: `tests/mcp/test_mcp_http.py`

**Error Testing:**
```python
def test_report_cli_error_returns_typer_exit_and_writes_log(tmp_path, capsys):
    exc = SearchTimeoutError("hung")
    result = report_cli_error(exc, command="multi")
    assert isinstance(result, typer.Exit)
    assert result.exit_code == 1
```
Source: `tests/cli/test_errors.py`

**Private module testing:**
- Import underscored helpers directly for branch coverage:
```python
from fli.search._decoders import ...
from fli.mcp.server import _serialize_flight_leg, _airline_code
```
Document intent in module docstring (`tests/search/test_decoders.py`, `tests/mcp/test_mcp_server_unit.py`).

**Live vs offline policy:**
| Category | Default `make test` | `make test-all` | Notes |
|----------|--------------------|-----------------|-------|
| `tests/cli/`, `tests/core/`, `tests/models/`, `tests/mcp/test_mcp_server_unit.py` | ✅ Included | ✅ Included | Reliable |
| `tests/search/` (live) | ❌ Ignored | ✅ Included | Flaky / rate-limited |
| Fuzz (`@pytest.mark.fuzz`) | ❌ Deselected | ✅ Included | Live API, slow |
| `tests/mcp/test_mcp_server.py` (live) | ⚠️ Included | ✅ Included | May fail on empty API results |
| `tests/app/` | ❌ Missing | ❌ Missing | v1.1 goal |

## CI Integration

**Workflow:** `.github/workflows/ci.yml`

**Lint job:**
- `uv run ruff format . --check`
- `uv run ruff check .`

**Test job (matrix Python 3.10–3.13):**
```bash
uv run pytest tests/ --all -v \
  --ignore=tests/search/ \
  -k "not test_search_dates_round_trip" \
  --junitxml=junit.xml
```
- Publishes JUnit XML via `publish-unit-test-result-action`
- Does not upload Python coverage artifacts

**Local CI mirror:**
```bash
make ci    # act -j lint -j test (requires Docker + act)
```

## Where to Add New Tests

**New `fli/` module:**
- Add `tests/<package>/test_<module>.py` mirroring source path.
- Prefer unit tests with mocks; add snapshot fixture only if testing response parsing.

**New CLI command:**
- Add tests in `tests/cli/test_<command>.py`.
- Reuse `mock_search_flights` / `mock_search_dates` from `tests/cli/conftest.py`.
- Add `runner` fixture locally or import shared pattern.

**New MCP tool:**
- Unit tests for serializers/helpers in `tests/mcp/test_mcp_server_unit.py` or new file.
- Optional integration test in `tests/mcp/` (note live API flakiness).

**New `app/` endpoint (v1.1):**
- Create `tests/app/conftest.py` with FastAPI `TestClient` fixture and mocked `SearchFlights`/engine.
- Add `tests/app/test_server.py`, `tests/app/test_engine.py` per `.planning/REQUIREMENTS.md`.
- Mock external Google API; test null-price filtering regression (`app/engine.py`).

**New script:**
- Add `tests/scripts/test_<script>.py` following `tests/scripts/test_bump_version.py` (tmp paths, monkeypatch git/subprocess).

---

*Testing analysis: 2026-06-18*
