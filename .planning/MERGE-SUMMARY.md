# Upstream Merge Summary — Milestone v1.0

**Date:** 2026-05-30  
**Merge commit:** `78866c5`  
**Pre-merge tag:** `pre-upstream-v1.0` (`d051b03`)  
**Upstream:** https://github.com/punitarani/fli (`origin/main`, 31 commits)

## What was merged

| Area | Upstream changes adopted |
|------|-------------------------|
| Python library | v0.8.5 → **v0.10.0**; booking deep-links, search refactor (`_proto`, `_wire`, `_decoders`), new filters |
| MCP | Expanded server, unit tests |
| CLI | New error handling, filter options, display updates |
| TypeScript | New `fli-js/` package (in repo, not wired to web UI) |
| CI/docs | Unified `ci.yml`, npm publish workflows, docs split python/typescript |
| Tests | Stubbed search fixtures, booking URL tests, concurrency tests |

## Local customizations preserved

| Component | Status |
|-----------|--------|
| `app/` FastAPI tracker + static UI | ✅ Working |
| `hot_core.py` hotel search | ✅ Working (sys.path import unchanged) |
| Root scripts (`track_my_flight.py`, etc.) | ✅ Present |
| Local `pyproject.toml` deps (FastAPI, plotext, etc.) | ✅ Merged cleanly |
| Audit fixes (F-01–F-05) | ✅ Retained |

## Local adaptations after merge

1. **`app/engine.py`** — Skip `FlightResult` entries with `price=None`; safe sort key (upstream can return unpriced itineraries)
2. **`tests/cli/test_utils.py`** — Date link test asserts `google_flights_url()` call + caption (Rich table links don't emit URLs to StringIO)

## Verification results

| Check | Result |
|-------|--------|
| `make lint` | ✅ Pass |
| `pytest` (excl. live API tests) | ✅ 711 passed |
| CLI smoke | ✅ JFK→LAX JSON search |
| MCP tests | ✅ 63+ passed |
| App smoke (Phase 3) | ✅ All `/api/*` routes |

## Git remotes

- `origin` → upstream (read-only pull source)
- `personal` → `larrycorsini/fli-tracker-personal` (push target after verification)

## Rollback

```bash
git reset --hard pre-upstream-v1.0   # or merge-base 1cb0231
```

## Deferred (future milestones)

- Move `hot_core.py` into `app/hotels.py`
- Remove superseded `flight_gui.py`
- Add `app/` test coverage
- Surface booking deep-links in tracker web UI
- Evaluate `fli-js` for frontend
