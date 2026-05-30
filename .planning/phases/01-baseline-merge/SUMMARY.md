# Phase 1 Summary: Baseline & Merge

**Completed:** 2026-05-30
**Merge commit:** `78866c5`

## What was done

### Plan 01-01: Baseline & analysis
- Tagged pre-merge baseline: `pre-upstream-v1.0` at `d051b03`
- Fetched `origin/main` (31 commits behind)
- Dry-run merge previously showed clean auto-merge on `pyproject.toml` / `uv.lock`

### Plan 01-02: Execute merge
- Merged `origin/main` into local `main` with merge commit `78866c5`
- **No manual conflict resolution required** — ort strategy auto-merged lockfiles
- `uv sync --all-extras` succeeded; package version now **0.10.0**
- Local-only paths verified present: `app/`, `hot_core.py`, `track_my_flight.py`, etc.

## Upstream adopted (highlights)

- `fli-js/` TypeScript port (new, not integrated into web UI yet)
- Booking deep-links: `fli/core/links.py`, search `_proto`, `_wire`, `_decoders`
- Major MCP server expansion, new CLI filters, CI workflow consolidation
- Examples reorganized under `examples/python/` and `examples/typescript/`

## Local preserved

- FastAPI tracker app (`app/server.py`, `app/engine.py`, `app/tracker.py`, static UI)
- Hotel search via `hot_core.py`
- Personal root scripts and JSON trip snapshots
- Local audit fixes (fuzz marker, asyncio, uv paths, playwright removed, `*.db` gitignored)
- Local deps in `pyproject.toml`: FastAPI, uvicorn, plotext, etc.

## Verification

| Check | Result |
|-------|--------|
| MERGE-01 merge commit | ✅ `78866c5` |
| MERGE-02 local paths | ✅ All present |
| MERGE-03 deps sync | ✅ `uv sync --all-extras` OK |
| MERGE-04 no conflicts | ✅ Clean merge |
| `app.engine` imports | ✅ OK |
| `fli.core.links` | ✅ Present |

## Notes for Phase 2+

- One upstream CLI test fails: `test_display_date_results_links_dates_when_route_given` (output format change — not blocking merge)
- Full test suite not run in Phase 1 (deferred to Phase 4)
- Push to `personal` remote not done (Phase 4, user-approved)
