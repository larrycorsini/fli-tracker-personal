# Technology Stack

**Analysis Date:** 2026-06-18

## Languages

**Primary:**
- Python 3.10+ (requires `>=3.10` per `pyproject.toml`) — core library (`fli/`), tracker app (`app/`), CLI, MCP server, tests
- TypeScript 6.x (ES2022 target) — `fli-js/` port of the Python library
- JavaScript (vanilla) — tracker SPA in `app/static/app.js`, static reports in `public/`
- HTML/CSS — `app/static/index.html`, `app/static/styles.css`, generated static pages in `public/`
- Shell (bash) — automation scripts (`daily_flight_search.sh`, `Makefile`)

**Secondary:**
- AppleScript (via `osascript`) — local iMessage alerts in `alert.py`
- Markdown — documentation (`docs/`, `mkdocs.yml`)

## Runtime

**Environment:**
- Python 3.10–3.13 (CI matrix in `.github/workflows/ci.yml`; production Docker/Railway uses 3.12)
- Bun >=1.1.0 or Node >=20.0.0 for `fli-js/` (`fli-js/package.json` `engines`)

**Package Manager:**
- **Python:** `uv` (Astral) — primary install/sync tool; lockfile `uv.lock` present
- **JavaScript:** Bun — `fli-js/bun.lock` with `bun install --frozen-lockfile` in CI
- Lockfile: present for both Python (`uv.lock`) and JS (`fli-js/bun.lock`)

## Frameworks

**Core:**
- **Typer** 0.16.0 — CLI framework (`fli/cli/main.py`, commands in `fli/cli/commands/`)
- **Pydantic** 2.11.7 — data models (`fli/models/`, `app/models.py`)
- **FastAPI** 0.116.1 — tracker HTTP API (`app/server.py`)
- **Uvicorn** 0.35.0 — ASGI server for tracker (`fli-tracker` entry point) and MCP HTTP mode
- **FastMCP** 3.2.0 — MCP server (`fli/mcp/server.py`)
- **sse-starlette** 3.0.2 — Server-Sent Events for flight search streaming (`app/server.py`)

**Testing:**
- **pytest** 8.4.1 + **pytest-asyncio** 1.1.0 + **pytest-xdist** + **pytest-cov** — Python tests (`tests/`)
- **Bun test runner** — TypeScript tests (`fli-js/tests/`); E2E gated by `FLI_E2E=1`

**Build/Dev:**
- **Hatchling** — Python wheel build (`pyproject.toml` `[build-system]`)
- **Ruff** 0.12.8 — Python lint + format (`Makefile`, `pyproject.toml` `[tool.ruff]`)
- **Biome** 2.4.15 + **oxlint** 1.66.0 — `fli-js/` format/lint
- **TypeScript** 6.0.3 (`tsc`) — `fli-js` build to `dist/`
- **MkDocs Material** 9.6.16 — docs site (`mkdocs.yml`, `make docs`)
- **Docker** multi-stage — MCP image (`Dockerfile`)
- **Nixpacks** — Railway deployment build (`nixpacks.toml`, `railway.toml`)

## Key Dependencies

**Critical (Python — flight search):**
- **curl-cffi** 0.13.0 — browser-impersonating HTTP client for Google Flights API (`fli/search/client.py`)
- **tenacity** 9.1.2 — retry with exponential backoff (`fli/search/client.py`)
- **ratelimit** 2.2.1 — global 10 req/sec token bucket (`fli/search/_concurrency.py`)
- **httpx** 0.28.1 — HTTP client for Google Hotels API (`app/hotels.py`)
- **babel** 2.17.0 — locale/currency formatting (`fli/core/currency.py`)
- **python-dotenv** 1.1.1 — listed in core deps (minimal runtime use; env vars read via `os.environ` in practice)
- **plotext** 5.3.2 — terminal charting in CLI (`fli/cli/`)

**Critical (TypeScript — fli-js):**
- **zod** 4.4.3 — runtime validation (`fli-js/src/`)
- Native **fetch** (Bun/Node) — replaces Python `curl-cffi` (`fli-js/src/search/client.ts`)

**Infrastructure:**
- **sqlite3** (stdlib) — tracker persistence (`app/tracker.py`, `app/data/tracker.db`)
- **pydantic-settings** — MCP config with `FLI_MCP_` prefix (`fli/mcp/server.py`)
- **Rich** (via Typer) — CLI console output (`fli/cli/console.py`)

## Configuration

**Environment:**
- No committed `.env` file detected; configuration via process environment
- Key runtime env vars:
  - `FLI_TIMEOUT` — HTTP timeout seconds (`fli/search/client.py`, `fli-js/src/search/client.ts`)
  - `HOST`, `PORT` — MCP HTTP bind (`fli/mcp/server.py`, `Dockerfile`)
  - `FLI_MCP_*` — MCP defaults (`fli/mcp/server.py` `FlightSearchConfig`)
  - `HTTPS_PROXY` / `HTTP_PROXY` — proxy for `fli-js` client
  - `FLI_E2E=1` — enable live API E2E tests (`fli-js/tests/e2e/`)
  - `GOOGLE_ANALYTICS_KEY` — MkDocs analytics (`mkdocs.yml`, docs build only)
  - `GITHUB_OUTPUT` — release scripts (`scripts/bump_version.py`)

**Build:**
- `pyproject.toml` — Python package metadata, scripts, ruff/pytest config
- `uv.lock` — pinned Python dependency tree
- `fli-js/package.json`, `fli-js/tsconfig.json`, `fli-js/tsconfig.build.json`, `fli-js/biome.json`
- `Makefile` — dev commands (`install`, `lint`, `test`, `mcp`, `docs`)
- `railway.toml`, `nixpacks.toml` — Railway/Nixpacks deploy
- `Dockerfile` — GHCR multi-arch MCP image (`.github/workflows/docker.yml`)

## Platform Requirements

**Development:**
- `uv sync --all-extras` or `make install-dev` for Python
- `cd fli-js && bun install` for TypeScript
- Docker optional (`.devcontainer/`, `make ci` via `act`)
- macOS-specific: `alert.py` iMessage via AppleScript; `daily_flight_search.sh` uses launchd paths

**Production:**
- **Railway** — MCP HTTP server (`fli-mcp-http`, `railway.toml`, Nixpacks Python 3.12 + uv)
- **GitHub Container Registry** — Docker image for MCP (`ghcr.io/<repo>`, `Dockerfile`)
- **GitHub Pages** — library docs (`.github/workflows/docs.yml`)
- **PyPI** — `flights` package (`.github/workflows/release.yml`, `publish.yml`)
- **npm** — `fli-js` package (`.github/workflows/release-npm.yml`, `publish-npm.yml`)
- **Netlify** — static report deploy from `public/` (`daily_flight_search.sh` uses `netlify-cli`)
- **Local tracker** — `uv run uvicorn app.server:app --reload` or `uv run fli-tracker` on port 8000

## Entry Points

| Command | Module | Purpose |
|---------|--------|---------|
| `fli` | `fli.cli:cli` | CLI flight/date search |
| `fli-mcp` | `fli.mcp._entry:run` | MCP STDIO server |
| `fli-mcp-http` | `fli.mcp._entry:run_http` | MCP HTTP server |
| `fli-tracker` | `app.server:main` | FastAPI tracker + static UI |

## Repository Layout (stack-relevant)

```
Fli-tracker/
├── fli/              # Python library (search, CLI, MCP, models)
├── app/              # FastAPI tracker (engine, server, SQLite, static SPA)
├── fli-js/           # TypeScript port (published as fli-js on npm)
├── tests/            # Python pytest suite
├── data/             # Source CSVs for airport/airline enum generation
├── docs/             # MkDocs source
├── public/           # Static HTML reports + PWA (Netlify)
├── scripts/          # Version bump, release helpers
└── examples/         # Python + TypeScript usage examples
```

---

*Stack analysis: 2026-06-18*
