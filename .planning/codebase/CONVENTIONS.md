# Coding Conventions

**Analysis Date:** 2026-06-18

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules (e.g. `fli/search/flights.py`, `tests/cli/test_errors.py`).
- Prefix internal implementation modules with `_` when they are not part of the public API (e.g. `fli/search/_wire.py`, `fli/search/_decoders.py`, `fli/search/_proto.py`, `fli/search/_helpers.py`, `fli/search/_urls.py`, `fli/search/_concurrency.py`).
- Test files mirror the source module they cover: `tests/<package>/test_<module>.py` maps to `fli/<package>/<module>.py`.

**Functions:**
- Use `snake_case` for all functions and methods (e.g. `resolve_enum`, `search_with_retry`, `report_cli_error`).
- Prefix module-private helpers with `_` (e.g. `_friendly_message`, `_write_log`, `_wrap_request_error`, `_host_from_url`).
- CLI/MCP handler functions use descriptive verb phrases (`search_flights`, `parse_airlines`, `_execute_flight_search`).

**Variables:**
- Use `snake_case` for locals, parameters, and module-level non-constants (e.g. `basic_search_params`, `log_path`, `future_date`).
- Use `UPPER_SNAKE_CASE` for module-level constants (e.g. `_LOG_DIR` in `fli/cli/errors.py`, `BG_CHECK_INTERVAL` in `app/server.py`, `EXPECTED_TOOLS` in `tests/mcp/test_mcp_http.py`).

**Types:**
- Use `PascalCase` for classes, enums, and Pydantic models (e.g. `FlightSearchFilters`, `SearchClientError`, `ParseError`, `TrackerDB`).
- Enum members use `UPPER_SNAKE_CASE` (e.g. `SeatType.ECONOMY`, `MaxStops.NON_STOP`, `Airport.JFK`).
- Type aliases and `TypeVar` names use single uppercase letters or `PascalCase` (e.g. `T = TypeVar("T", bound=Enum)` in `fli/core/parsers.py`).

**Test naming:**
- Test functions: `test_<behavior>` (e.g. `test_basic_flights_search`, `test_write_log_creates_file_with_traceback`).
- Test classes (optional, used for grouping): `Test<Component>` (e.g. `TestWrapRequestError`, `TestSerializeFlightLeg`, `TestMCPServer`).
- Fixture functions: short `snake_case` nouns (e.g. `runner`, `search`, `mock_search_flights`, `basic_search_params`).
- Parametrize IDs: descriptive strings or generated via helper (e.g. `ids=[tc["name"] for tc in TEST_CASES]` in `tests/models/test_flight_search_filters.py`).

## Code Style

**Formatting:**
- Tool: **Ruff formatter** (`uv run ruff format`).
- Line length: **100** characters (`pyproject.toml` → `[tool.ruff]`).
- Indentation: **4 spaces** (`indent-width = 4`, `indent-style = "space"`).
- Quotes: **double** (`quote-style = "double"`).
- Trailing commas: keep magic trailing commas (`skip-magic-trailing-comma = false`).

**Linting:**
- Tool: **Ruff check** (`uv run ruff check`).
- Enabled rule sets: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (flake8-bugbear), `C4` (comprehensions), `UP` (pyupgrade), `D` (pydantic-style docstrings).
- Ignored docstring rules globally: `D100`, `D104`, `D203`, `D213`.
- Per-file ignores in `examples/**/*.py`: relax `D101`–`D103`, `D401`, allow `T201` (print).
- Per-file ignores in `tests/**/*.py`: relax `D101`–`D103` (tests do not require class/method/function docstrings).

**Lint/format scope (important):**
- Ruff `include` covers `fli/`, `examples/`, `tests/`, `scripts/` only — **`app/` is not included**.
- `Makefile` `TARGETS` is `fli/ scripts/ tests/` — run `ruff format app/` and `ruff check app/` manually until `app/` is added to targets.
- Target Python version: `py310` (`target-version = "py310"`).

**Make commands:**
```bash
make format    # ruff format fli/ scripts/ tests/
make lint      # ruff check fli/ scripts/ tests/
make lint-fix  # ruff check --fix fli/ scripts/ tests/
```

## Import Organization

**Order (enforced by Ruff isort `I`):**
1. `from __future__ import annotations` when used (first line after module docstring).
2. Standard library imports.
3. Third-party imports (`pytest`, `typer`, `pydantic`, `fastapi`, etc.).
4. First-party `fli.*` or `app.*` imports.

**Path aliases:**
- No import path aliases; use full package paths (`from fli.models import Airport`, `from fli.search import SearchFlights`, `from app.engine import search_flights_async`).

**Lazy imports:**
- Defer heavy imports until needed. Example in `fli/search/client.py`: `curl_cffi` is imported lazily; `TYPE_CHECKING` block provides types without runtime cost.

**Example pattern from `fli/core/parsers.py`:**
```python
"""Module docstring."""

import re
from enum import Enum
from typing import TypeVar

from fli.models import (
    Airline,
    Airport,
    ...
)
```

## Type Hints

- Require type hints on all public function signatures in `fli/` (Python 3.10+ syntax).
- Prefer modern union syntax: `str | None`, `list[str]`, `dict[str, Any]` over `Optional`, `List`, `Dict`.
- Use `from __future__ import annotations` in modules that benefit from forward references (common in `fli/search/`, `fli/cli/errors.py`).
- Pydantic models in `fli/models/` and `app/models.py` carry validation via field types and validators.

## Error Handling

**Typed exception hierarchies:**
- Search/network errors: `fli/search/exceptions.py` — `SearchClientError` base with `SearchTimeoutError`, `SearchConnectionError`, `SearchHTTPError` (stores `status_code`).
- Parse errors: `ParseError(ValueError)` in `fli/core/parsers.py`.
- Always chain underlying exceptions: `raise ParseError(...) from e`.

**CLI error reporting (`fli/cli/errors.py`):**
- Map typed search errors to user-facing messages via `_friendly_message`.
- Write full tracebacks to `~/.fli/logs/fli-error-<timestamp>.log` via `_write_log`.
- Return `typer.Exit` from `report_cli_error` — callers `raise` it to suppress raw tracebacks.
- JSON mode uses `json_error_payload` returning `(message, error_type, log_path)`.

**HTTP client errors (`fli/search/client.py`):**
- Wrap `curl_cffi` exceptions in `_wrap_request_error` → typed `SearchClientError` subclasses.
- Retries via `tenacity` (`retry`, `stop_after_attempt`, `wait_exponential`) on the client layer.

**MCP server (`fli/mcp/server.py`):**
- Tool handlers catch exceptions and return structured `{success: False, error: ...}` dicts rather than leaking stack traces to clients.
- Unit tests in `tests/mcp/test_mcp_server_unit.py` cover error propagation paths explicitly.

**App layer (`app/server.py`):**
- Background tasks log errors and continue (`logger.error` in `_background_price_checker`).
- FastAPI routes return `JSONResponse` with appropriate status codes.
- Not yet covered by the shared `fli` error-reporting helpers.

**Testing errors:**
- Redirect log directories in tests with `monkeypatch.setattr("fli.cli.errors._LOG_DIR", tmp_path / "fli-logs")` (`tests/cli/test_errors.py`).
- Parametrize exception types for payload mapping tests.

## Logging

**Framework:** Python standard `logging` module.

**Patterns:**
- CLI: `logging.getLogger("fli")` — debug-level `exc_info` in `report_cli_error` (`fli/cli/errors.py`).
- Tracker app: `logging.getLogger("server")` with `logging.basicConfig(level=logging.INFO)` at import (`app/server.py`).
- Do not use `print` in library code (`fli/`); examples are exempt (`T201` ignored).

## Comments

**When to Comment:**
- Module docstrings: always in `fli/` public modules — explain purpose and consumers.
- Non-obvious business logic: wire-format positions, API quirks, threading model (see `fli/search/client.py` threading section).
- Test fixture drift policy: document in module docstring when tests depend on captured snapshots (`tests/search/test_snapshot_fixtures.py`).

**Docstrings (Google style):**
- Module: one-line or short paragraph summary.
- Functions: `Args:`, `Returns:`, `Raises:` sections where non-trivial (`fli/core/parsers.py`).
- Classes: brief description; Pydantic models often self-document via fields.
- Tests: module docstring encouraged; per-test docstrings optional (one-line `"""Test X."""` is common).

**Avoid:**
- Commenting obvious code.
- Leaving `TODO` in production paths without issue reference (one exists in `tests/search/test_search_flights.py` for round-trip live tests).

## Function Design

**Size:** Keep functions focused; extract helpers for parsing, serialization, and wire encoding. Large modules (`fli/mcp/server.py`, `fli/search/flights.py`) split internals into `_*.py` submodules.

**Parameters:**
- Prefer keyword-only for optional behavior (`*, command: str | None = None` in `report_cli_error`).
- CLI/MCP expose user-facing names (`origin`, `destination`, `cabin_class`, `max_stops`) — shared parsing in `fli/core/parsers.py` and `fli/core/builders.py`.

**Return Values:**
- Parsers/builders return domain models or `None` for empty optional input.
- Search methods return `list[FlightResult]` or structured dicts for round trips.
- CLI commands exit via `typer.Exit` or `raise report_cli_error(...)`.

## Module Design

**Exports:**
- Package `__init__.py` files re-export public API (e.g. `from fli.search import SearchFlights`).
- Keep wire/protocol details in `_`-prefixed modules; tests may import privates for branch coverage (`tests/search/test_decoders.py`).

**Barrel Files:**
- Minimal `__init__.py` re-exports; no heavy logic in package roots.

**Shared utilities:**
- Cross-interface parsing/building: `fli/core/parsers.py`, `fli/core/builders.py`, `fli/core/airports.py`, `fli/core/currency.py`.
- Both CLI (`fli/cli/`) and MCP (`fli/mcp/server.py`) consume core utilities — add new filter parsing here, not duplicated per interface.

## Domain Patterns

**Pydantic models:**
- All Google Flights structures live under `fli/models/google_flights/` (`flights.py`, `dates.py`, `base.py`).
- Enums for airports/airlines in `fli/models/airport.py`, `fli/models/airline.py`.
- Validate at model construction; tests use real model instances, not raw dicts, unless testing serialization.

**CLI (Typer):**
- Entry: `fli/cli/main.py` — registers `airports`, `dates`, `flights`, `multi`.
- Commands in `fli/cli/commands/`; shared console output via `fli/cli/console.py` and `fli/cli/utils.py`.
- Smart default: bare args route to `flights` command.

**MCP (FastMCP):**
- Server: `fli/mcp/server.py`; entry points `fli/mcp/_entry.py` (`fli-mcp`, `fli-mcp-http` scripts).
- Params models: `FlightSearchParams`, `DateSearchParams` — parallel CLI argument shapes.

**Tracker app (`app/`):**
- FastAPI in `app/server.py`; business logic in `app/engine.py`, `app/tracker.py`, `app/hotels.py`.
- Pydantic request models in `app/models.py`.
- Follow same typing and naming as `fli/`, but **not yet enforced by Ruff/Makefile targets**.

---

*Convention analysis: 2026-06-18*
