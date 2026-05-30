# Testing Patterns

**Analysis Date:** 2026-05-30

## Test Framework

**Runner:**
- pytest 8.3.4
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`
- No separate `pytest.ini` or `setup.cfg`

**Assertion Library:**
- pytest's built-in `assert` statements (no third-party assertion library)

**Async support:**
- pytest-asyncio 0.25.2 — for `@pytest.mark.asyncio` async test methods

**Parallelism:**
- pytest-xdist 3.6.1 — available for parallel execution via `@pytest.mark.parallel`

**Coverage:**
- pytest-cov 6.0.0 — installed but no minimum coverage threshold enforced

**CLI testing:**
- `typer.testing.CliRunner` — used for all CLI command tests

**Run Commands:**
```bash
make test            # Standard suite (excludes fuzz tests)
make test-mcp        # MCP tests only (--mcp flag)
make test-fuzz       # Fuzz tests only (--fuzz flag)
make test-all        # All tests including fuzz (--all flag)

uv run pytest -vv                         # Direct invocation
uv run pytest -vv --ignore=tests/search/  # Skip live API tests (CI-safe)
uv run pytest tests/ --all -v --ignore=tests/search/ -k "not test_search_dates_round_trip" --junitxml=junit.xml  # CI command
```

## Test File Organization

**Location:** Separate `tests/` directory at repo root — NOT co-located with source.

**Structure mirrors source:**
```
tests/
├── conftest.py                        # Global fixtures and custom pytest hooks
├── cli/
│   ├── conftest.py                    # CLI-specific fixtures (mock_search_flights, mock_search_dates, mock_console)
│   ├── test_airports.py
│   ├── test_dates.py
│   ├── test_flights.py
│   ├── test_multi.py
│   └── test_utils.py
├── core/
│   ├── test_airports.py
│   ├── test_builders.py
│   ├── test_currency.py
│   └── test_parsers.py
├── mcp/
│   ├── test_find_airports.py
│   ├── test_mcp_http.py
│   ├── test_mcp_server.py
│   ├── test_mcp_server_fixes.py
│   └── test_multi_airport.py
├── models/
│   ├── test_date_search_filters.py
│   ├── test_date_search_filters_validation.py
│   ├── test_flight_search_filters.py
│   ├── test_flight_segment_validation.py
│   └── test_time_restrictions.py
└── search/
    ├── test_search_dates.py
    ├── test_search_flights.py
    └── test_search_flights_fuzz.py     # Gated behind --fuzz flag
```

**Naming:**
- Test files: `test_<module_name>.py`
- Test functions: `def test_<description>()` in snake_case
- Test classes: `class Test<FeatureName>:` in PascalCase

## Custom Pytest Flags and Markers

**Custom CLI flags** (registered in `tests/conftest.py`):
- `--fuzz` — enables fuzz tests; without `--all`, also restricts collection to fuzz-only tests
- `--mcp` — restricts collection to MCP tests only
- `--all` — runs everything including fuzz tests

**Custom markers** (registered in `pyproject.toml`):
- `@pytest.mark.fuzz` — marks tests that generate random inputs against the live API; requires `--fuzz` or `--all`
- `@pytest.mark.parallel` — marks tests safe for parallel execution with pytest-xdist

**Skip logic** (`tests/conftest.py`):
```python
def pytest_runtest_setup(item) -> None:
    fuzz_marker = item.get_closest_marker("fuzz")
    if fuzz_marker is not None:
        if not item.config.getoption("--fuzz") and not item.config.getoption("--all"):
            pytest.skip("need --fuzz or --all option to run this test")
```

## Test Structure

**Class-based grouping** (used for related method tests):
```python
class TestMCPServer:
    """Test suite for MCP server tools."""

    def test_search_flights_one_way(self):
        """Test one-way flight search."""
        ...

    def test_search_flights_round_trip(self):
        """Test round-trip flight search."""
        ...
```

**Function-based tests** (preferred for isolated model/validation tests):
```python
def test_time_restrictions_departure_swap():
    """Test TimeRestrictions auto-swaps departure times when out of order."""
    tr = TimeRestrictions(
        earliest_departure=20,
        latest_departure=9,
        ...
    )
    assert tr.earliest_departure == 9
```

## Fixtures

**Defined in:**
- `tests/conftest.py` — global fixtures (`pytest_addoption`, `pytest_runtest_setup`, `pytest_collection_modifyitems`)
- `tests/cli/conftest.py` — CLI-scope fixtures used across all CLI test files

**Key shared fixtures** (in `tests/cli/conftest.py`):
- `mock_search_flights` — MagicMock patching `SearchFlights.__new__` via `monkeypatch.setattr`; returns pre-built `FlightResult` objects
- `mock_search_dates` — MagicMock patching `SearchDates.__new__`
- `mock_console` — MagicMock patching `fli.cli.utils.console` to suppress rich output during tests

**Local fixtures** (in individual test files):
- `runner` — `typer.testing.CliRunner()` instance
- `future_date` — `datetime.now() + timedelta(days=30)` helper
- `http_mcp_url` — boots uvicorn on a free port in a background thread, yields the base URL, tears down on exit

## Mocking

**Framework:** `unittest.mock.MagicMock` combined with pytest's `monkeypatch`.

**Pattern: Patch `__new__` to intercept class instantiation:**
```python
@pytest.fixture
def mock_search_flights(monkeypatch):
    mock = MagicMock()
    mock.search.return_value = [FlightResult(...)]
    monkeypatch.setattr("fli.search.flights.SearchFlights.__new__", lambda cls: mock)
    monkeypatch.setattr("fli.search.SearchFlights.__new__", lambda cls: mock)
    return mock
```

**What to mock:**
- `SearchFlights` and `SearchDates` in CLI and MCP tests — avoids live API calls
- `fli.cli.utils.console` — suppresses rich terminal output in test runs

**What NOT to mock:**
- Pydantic model construction — test the real models with valid/invalid data
- `fli/core/` parsing/building logic — these are pure functions, test them directly
- `fli/models/` enums and validators — test real validation behavior

## Parametrize

**Pattern:** `@pytest.mark.parametrize` with named test cases for model validation:
```python
TEST_CASES = [
    {
        "name": "Test 1: Flight Search Data",
        "search": FlightSearchFilters(...),
        "formatted": [...],
        "encoded": None,
    },
    ...
]

@pytest.mark.parametrize("test_case", TEST_CASES, ids=[tc["name"] for tc in TEST_CASES])
def test_flight_search_filters(test_case):
    """Test FlightSearchFilters formatting and encoding with various configurations."""
    formatted_filters = test_case["search"].format()
    assert formatted_filters == test_case["formatted"]
```

See `tests/models/test_flight_search_filters.py` for the canonical parametrize pattern.

## Async Testing

**Pattern:** `@pytest.mark.asyncio` on async test methods within test classes:
```python
class TestMCPInProcess:
    @pytest.mark.asyncio
    async def test_list_tools_returns_expected_names(self):
        client = Client(mcp)
        async with client:
            tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == EXPECTED_TOOLS
```

**Used in:** `tests/mcp/test_mcp_http.py`, `tests/mcp/test_mcp_server_fixes.py`

## Dynamic Test Data

**Future date helper** (repeated pattern across test files):
```python
def get_future_date(days: int = 30) -> str:
    """Generate a future date string in YYYY-MM-DD format."""
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
```

Defined locally in each file that needs it (`tests/cli/conftest.py`, `tests/mcp/test_mcp_server.py`, `tests/models/test_flight_search_filters.py`). Use this pattern to avoid hardcoded dates that would expire.

## Error/Validation Testing

**Pattern for expected exceptions:**
```python
def test_flight_segment_past_date():
    past = datetime.now() - timedelta(days=1)
    with pytest.raises(ValueError, match="Travel date cannot be in the past"):
        FlightSegment(
            departure_airport=[[Airport.PHX, 0]],
            arrival_airport=[[Airport.SFO, 0]],
            travel_date=past.strftime("%Y-%m-%d"),
        )
```

**Custom `ParseError`:**
```python
with pytest.raises(ParseError, match="Invalid EmissionsFilter"):
    parse_emissions("NONE")
```

## Fuzz Testing

**Location:** `tests/search/test_search_flights_fuzz.py`

**Pattern:** Generates randomized test cases with `random.seed(42)` for reproducibility, then runs live API searches:
```python
@pytest.mark.fuzz
@pytest.mark.parallel
@pytest.mark.parametrize("dep_airport,arr_airport,dep_date,...", generate_random_test_cases(10))
def test_search_flights_fuzz(search, dep_airport, arr_airport, dep_date, ...):
    ...
```

Fuzz tests hit the live Google Flights API and are excluded from standard test runs.

## Test Types

**Unit Tests:**
- `tests/models/` — Pydantic model validation (no I/O)
- `tests/core/` — Pure parsing/building functions (no I/O)
- Fully self-contained; always pass in CI

**Integration Tests (mocked):**
- `tests/cli/` — CLI commands with `SearchFlights`/`SearchDates` mocked out
- `tests/mcp/` — MCP server tools with in-process FastMCP client

**Integration Tests (live API):**
- `tests/search/` — Direct Google Flights API calls; excluded from CI with `--ignore=tests/search/`
- One MCP test (`test_search_dates_round_trip`) also makes a live call; excluded in CI with `-k "not test_search_dates_round_trip"`

**HTTP Integration Tests:**
- `tests/mcp/test_mcp_http.py` — Starts real uvicorn server in a background thread, connects via HTTP

**Fuzz Tests:**
- `tests/search/test_search_flights_fuzz.py` — Random inputs against live API; gated behind `--fuzz`

## Coverage

**Requirements:** No minimum coverage threshold configured.

**View Coverage:**
```bash
uv run pytest --cov=fli --cov-report=html
```

## CI Configuration

**Workflow:** `.github/workflows/test.yml`

**Matrix:** Python 3.10, 3.11, 3.12, 3.13 (all supported versions tested in parallel, `fail-fast: false`)

**Prerequisites:** Lint must pass before tests run (`needs: [lint, railway-build]`)

**CI test command:**
```bash
uv run pytest tests/ --all -v \
    --ignore=tests/search/ \
    -k "not test_search_dates_round_trip" \
    --junitxml=junit.xml
```

**Results:** JUnit XML artifacts uploaded per Python version; test results published as PR comments via `publish-unit-test-result-action`.

---

*Testing analysis: 2026-05-30*
