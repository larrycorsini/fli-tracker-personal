# Technology Stack

**Analysis Date:** 2026-05-30

## Languages

**Primary:**
- Python 3.10+ - All backend, library, CLI, MCP server, and app logic
- HTML/CSS/JavaScript - Frontend SPA (`app/static/index.html`, `app/static/styles.css`, `app/static/app.js`)

**Secondary:**
- TOML - Configuration files (`pyproject.toml`, `nixpacks.toml`, `railway.toml`, `mkdocs.yml`)

## Runtime

**Environment:**
- CPython 3.10, 3.11, 3.12, 3.13 (all supported; 3.12 used for production Docker image and CI builds)

**Package Manager:**
- uv (Astral) — lockfile-based (`uv.lock`, revision 3)
- Lockfile: present (`uv.lock`)
- Build backend: `hatchling`

## Frameworks

**Core (Library + MCP):**
- `fastmcp` >=3.2.0 - MCP (Model Context Protocol) server framework (`fli/mcp/server.py`)
- `fastapi` >=0.116.1 - Async REST API and SSE server (`app/server.py`)
- `uvicorn` >=0.35.0 - ASGI server for FastAPI (`app/server.py`)
- `pydantic` >=2.10.4 - Data models and validation (`fli/models/`, `fli/mcp/server.py`)
- `pydantic-settings` >=2.0.0 - MCP config from env vars (`fli/mcp/server.py` → `FlightSearchConfig`)
- `typer` >=0.15.1 - CLI interface (`fli/cli/`)

**HTTP Client:**
- `curl-cffi` >=0.7.4 - Browser-impersonating HTTP client; bypasses bot detection (`fli/search/client.py`)
- `httpx` >=0.28.1 - Standard async HTTP client used in `hot_core.py` for hotel search
- `playwright` >=1.58.0 - Browser automation (dependency declared; not actively used in primary paths as of this analysis)

**Streaming:**
- `sse-starlette` >=3.0.2 - Server-Sent Events for streaming flight search results (`app/server.py`)

**Utilities:**
- `babel` >=2.17.0 - Internationalization/locale support
- `plotext` >=5.3.2 - Terminal plotting (used in CLI output)
- `python-dotenv` >=1.0.1 - `.env` file loading for environment variables
- `ratelimit` >=2.2.1 - 10 req/sec decorator on HTTP client (`fli/search/client.py`)
- `tenacity` >=9.0.0 - Retry with exponential backoff (`fli/search/client.py`)

**Testing:**
- `pytest` >=8.3.4 - Test runner (`tests/`)
- `pytest-asyncio` >=0.25.2 - Async test support
- `pytest-xdist` >=3.6.1 - Parallel test execution
- `pytest-cov` >=6.0.0 - Coverage reporting
- `ruff` >=0.8.4 - Linter and formatter

**Build/Dev:**
- `mkdocs-material` >=9.5.49 with imaging - Documentation site (`docs/`, `mkdocs.yml`)
- `mkdocstrings[python]` >=0.27.0 - Auto-generated API docs from Google-style docstrings
- `twine` >=6.0.0 - PyPI publishing
- `tox` - Multi-environment testing (`tox.ini`)

## Key Dependencies

**Critical:**
- `curl-cffi` >=0.7.4 - Core to the entire library; enables TLS fingerprint impersonation needed to access Google Flights API without detection. Removing this breaks all flight search.
- `fastmcp` >=3.2.0 - Powers the MCP server (`fli-mcp`, `fli-mcp-http` entry points); exposes `search_flights`, `search_dates`, `find_airports` tools to AI assistants.
- `pydantic` >=2.10.4 - Used pervasively in `fli/models/` for all flight/filter data structures; breaking change would cascade across the entire library.
- `ratelimit` + `tenacity` - Together enforce 10 req/sec + 3-attempt retry policy. Removing either risks Google API bans.

**Infrastructure:**
- `fastapi` + `uvicorn` + `sse-starlette` - The `app/` Travel Planner Pro web server with SSE streaming for real-time flight results
- `httpx` - Hotel search in `hot_core.py` against Google Hotels `batchexecute` endpoint
- `typer` - CLI entry point `fli` command with `flights` and `dates` subcommands

## Configuration

**Environment:**
- No `.env` file committed; runtime config via environment variables
- MCP server config via `FLI_MCP_*` prefix (see `FlightSearchConfig` in `fli/mcp/server.py`)
  - `FLI_MCP_DEFAULT_PASSENGERS`, `FLI_MCP_DEFAULT_CURRENCY`, `FLI_MCP_DEFAULT_CABIN_CLASS`
  - `FLI_MCP_DEFAULT_SORT_BY`, `FLI_MCP_DEFAULT_DEPARTURE_WINDOW`, `FLI_MCP_MAX_RESULTS`
- Docker/deployment config: `HOST` and `PORT` env vars (default `0.0.0.0:8000`)

**Build:**
- `pyproject.toml` — package metadata, dependencies, ruff config, pytest markers
- `uv.lock` — pinned dependency graph
- `hatchling` build backend; wheel packages `fli` and `app`

## Platform Requirements

**Development:**
- Python >=3.10
- `uv` package manager (`uv sync --all-extras` to install all deps)
- Docker + `act` for local CI simulation (optional)

**Production:**
- Docker image: `python:3.12-slim` multi-stage build, runs `fli-mcp-http` on port 8000
- Published to GHCR: `ghcr.io/punitarani/fli:latest`
- Railway deployment: NIXPACKS builder using `nixpacks.toml`, Python 3.12, `uv` 0.11.3
- PyPI package: `flights` (published via GitHub Actions on release)
- Docs: GitHub Pages via MkDocs Material (`https://punitarani.github.io/fli`)

---

*Stack analysis: 2026-05-30*
