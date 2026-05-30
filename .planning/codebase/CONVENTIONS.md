# Coding Conventions

**Analysis Date:** 2026-05-30

## Naming Patterns

**Files:**
- `snake_case.py` for all source files (e.g., `parsers.py`, `search_flights.py`, `test_flight_segment_validation.py`)
- `_entry.py` prefix for internal/private module entry points (e.g., `fli/mcp/_entry.py`)
- Test files prefixed with `test_` mirroring the module they cover

**Classes:**
- `PascalCase` (e.g., `SearchFlights`, `FlightSearchFilters`, `ParseError`, `FlightSearchConfig`)
- Exception subclasses explicitly inherit the relevant base (e.g., `class ParseError(ValueError)`)

**Functions and Methods:**
- `snake_case` for all public functions and methods (e.g., `resolve_airport`, `parse_airlines`, `build_time_restrictions`)
- `_snake_case` prefix for internal module helpers (e.g., `_search_dates_from_params`, `_search_flights_from_params`)

**Constants and Class Attributes:**
- `UPPER_SNAKE_CASE` for module-level constants and class-level config (e.g., `BASE_URL`, `DEFAULT_HEADERS`, `TRAVEL_DATE`)
- `_LOWER_SNAKE_CASE` prefix for private module-level constants (e.g., `_AIRLINE_SEPARATORS`)

**Enums:**
- Enum member names in `UPPER_SNAKE_CASE` (e.g., `SeatType.PREMIUM_ECONOMY`, `MaxStops.NON_STOP`, `SortBy.TOP_FLIGHTS`)
- Enum classes in `PascalCase` inheriting `Enum` from stdlib

**Variables:**
- `snake_case` for all local variables and parameters

## Code Style

**Formatting:**
- Tool: Ruff formatter
- Line length: 100 characters
- Indent: 4 spaces (no tabs)
- Quote style: double quotes
- Magic trailing comma: preserved (`skip-magic-trailing-comma = false`)
- Config: `[tool.ruff.format]` in `pyproject.toml`

**Linting:**
- Tool: Ruff
- Enabled rule sets: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (flake8-bugbear), `C4` (flake8-comprehensions), `UP` (pyupgrade), `D` (pydocstyle)
- Ignored rules: `D100` (missing module docstring in public packages), `D104` (missing docstring in public package `__init__`), `D203` (one-blank-line-before-class), `D213` (multi-line-summary-second-line)
- Per-file ignores: `tests/**/*.py` exempts `D101`, `D102`, `D103` (no docstrings required in test classes/methods/functions); `examples/**/*.py` additionally exempts `T201` (print statements allowed)
- Config: `[tool.ruff.lint]` in `pyproject.toml`

## Docstrings

**Required on:**
- All public modules (module-level docstrings at top of every `.py` file)
- All public classes
- All public functions and methods

**Style:** Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections.

**First line:** Imperative mood (e.g., "Resolve an airport code", "Parse a list of airline codes") — enforced by `D401`.

**Example pattern from `fli/core/parsers.py`:**
```python
def resolve_airport(code: str) -> Airport:
    """Resolve an airport code to an Airport enum.

    Args:
        code: IATA airport code (e.g., 'JFK', 'LHR')

    Returns:
        The corresponding Airport enum member

    Raises:
        ParseError: If the code is not a valid airport

    """
```

## Import Organization

**Order (isort-enforced):**
1. Standard library imports
2. Third-party imports
3. Local/intra-package imports

**Example from `fli/core/parsers.py`:**
```python
import re
from enum import Enum
from typing import TypeVar

from fli.models import Airline, Airport, EmissionsFilter, MaxStops, SeatType, SortBy
```

**Path Aliases:**
- None — all imports use absolute package paths (`fli.models`, `fli.core`, `fli.search`)
- Intra-package relative imports only for `__init__.py` re-exports (e.g., `from .airline import Airline`)

**`__all__` Lists:**
- Explicit `__all__` defined in all `__init__.py` files to control public API surface
- See `fli/models/__init__.py`, `fli/core/__init__.py`

## Type Hints

**Coverage:** Full type annotations required on all function signatures including return types.

**Python 3.10+ Union Syntax:**
- Use `X | Y` instead of `Union[X, Y]` (enforced by `UP` pyupgrade rules)
- Use `X | None` instead of `Optional[X]`

**Pydantic Constraints:**
- Use Pydantic's typed constraints directly in model fields: `NonNegativeFloat`, `NonNegativeInt`, `PositiveInt`
- Use `Annotated[..., Field(...)]` for validation metadata in Pydantic models

**Example from `fli/models/google_flights/base.py`:**
```python
earliest_departure: NonNegativeInt | None = None
latest_departure: PositiveInt | None = None
```

## Pydantic Models

**Version:** Pydantic v2 (`BaseModel` from `pydantic`)

**Validators:**
- `@field_validator` with `@classmethod` for field-level validation
- `@model_validator` for cross-field logic
- Validators use `ValidationInfo` for accessing sibling field values

**Example from `fli/models/google_flights/base.py`:**
```python
@field_validator("latest_departure", "latest_arrival")
@classmethod
def validate_latest_times(
    cls, v: PositiveInt | None, info: ValidationInfo
) -> PositiveInt | None:
    ...
```

**Configuration via Settings:**
- Use `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_prefix="FLI_MCP_")` for env-driven config (see `fli/mcp/server.py`)

## Enums

**Pattern:** Standard Python `Enum` from stdlib, integer or string values depending on API needs.

**Enum values map directly to API constants:**
```python
class SeatType(Enum):
    ECONOMY = 1
    PREMIUM_ECONOMY = 2
    BUSINESS = 3
    FIRST = 4
```

**Never use bare strings** where an enum is defined — always resolve strings to enums via `resolve_enum()` in `fli/core/parsers.py`.

## Error Handling

**Custom Exception Classes:**
- `ParseError(ValueError)` in `fli/core/parsers.py` — raised when user-supplied string input cannot be resolved to an enum or model value

**Exception chaining:** Always use `raise NewException(...) from e` to preserve the original traceback:
```python
raise ParseError(f"Invalid airport code: '{code}'") from e
```

**HTTP errors:** `response.raise_for_status()` called immediately after every HTTP response.

**Broad except with re-raise:** Permitted in client layer for wrapping network errors with context:
```python
except Exception as e:
    raise Exception(f"GET request failed: {str(e)}") from e
```

**Validation errors:** Pydantic raises `ValueError` from validators; CLI catches and surfaces these as user-friendly messages.

## Logging

**Framework:** Standard library `logging` module.

**Usage:** Minimal — only in `fli/search/flights.py` for debug-level skipping of unparseable flight data:
```python
logging.debug("Skipping flight with unparseable data: %s", e)
```

No structured logging or log configuration setup is present in the codebase.

## Module Design

**Exports:** All public APIs surfaced through `__init__.py` with explicit `__all__` lists.

**Barrel files:** `fli/models/__init__.py` and `fli/core/__init__.py` re-export all public symbols; consumers always import from the top-level package (e.g., `from fli.models import Airport`).

**Layer separation:**
- `fli/models/` — pure data definitions (Pydantic models, enums)
- `fli/core/` — shared parsing/building utilities (no I/O)
- `fli/search/` — API client and search logic (I/O)
- `fli/cli/` — CLI commands (presentation)
- `fli/mcp/` — MCP server (presentation)

## Comments

**When to Comment:**
- Module-level docstrings to describe the module's purpose and context
- Section dividers with `# ===...===` and `# -------` for long files (e.g., `fli/mcp/server.py`)
- Inline comments to explain non-obvious API format requirements (e.g., Google Flights API structure)

**Avoid:** Comments that restate what the code does; prefer self-documenting names.

## Function Design

**Single responsibility:** Parsing functions each handle exactly one concern (e.g., `parse_airlines`, `parse_max_stops`, `parse_sort_by`).

**Early returns:** Used in validators and parsers to handle `None`/empty inputs before main logic.

**Parameters:** Prefer direct value parameters over dict-style `**kwargs` in domain functions; use `**kwargs` only in HTTP client pass-through methods.

---

*Convention analysis: 2026-05-30*
