# Requirements: Fli-Tracker — Milestone v1.0

**Defined:** 2026-05-30
**Core Value:** Tracker app keeps working while `fli` library stays current with upstream

## Milestone Requirements

### Merge & Integration

- [x] **MERGE-01**: Upstream `origin/main` is merged into local `main` with a merge commit
- [x] **MERGE-02**: All local-only paths remain present after merge (`app/`, `hot_core.py`, root scripts)
- [x] **MERGE-03**: `pyproject.toml` and `uv.lock` resolve correctly with both upstream and local dependencies
- [x] **MERGE-04**: No unresolved git merge conflicts remain

### Library Compatibility

- [x] **LIB-01**: `fli` CLI commands run successfully (`uv run fli flights JFK LAX 2026-06-15 --format json`)
- [x] **LIB-02**: MCP server starts without import errors (`uv run fli-mcp` smoke test)
- [x] **LIB-03**: `app/engine.py` flight and date search wrappers work with post-merge `fli/search/` API
- [x] **LIB-04**: Upstream booking link support is available in Python library (verify `fli/core/links.py` present)

### App Verification

- [x] **APP-01**: FastAPI server starts (`uv run uvicorn app.server:app`)
- [x] **APP-02**: Flight search API returns results via `/api/search/flights`
- [x] **APP-03**: Tracker CRUD endpoints respond (`/api/tracker/*`)
- [x] **APP-04**: Hotel search still works via `hot_core.py` integration in engine

### Quality & Documentation

- [x] **QA-01**: `uv run pytest -vv --ignore=tests/search/` passes (239+ tests)
- [x] **QA-02**: `make lint` passes with no new errors
- [x] **DOC-01**: Merge summary recorded in `.planning/` or commit message documenting adopted upstream changes

## Future Requirements

Deferred to later milestones.

### Cleanup

- **CLEAN-01**: Move `hot_core.py` into `app/hotels.py` and remove sys.path hack
- **CLEAN-02**: Archive or remove superseded `flight_gui.py`
- **CLEAN-03**: Add test coverage for `app/` module

### Features

- **FEAT-01**: Surface booking deep-links in tracker web UI
- **FEAT-02**: Evaluate fli-js for frontend integration

## Out of Scope

| Feature | Reason |
|---------|--------|
| fli-js frontend integration | New upstream surface; out of sync scope |
| Root script cleanup | Separate cleanup milestone |
| PyPI/npm publishing | Upstream release process |
| Full app/ test suite | Too large for merge milestone |
| Deleting local JSON trip snapshots | User data, not merge-related |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MERGE-01 | Phase 1 | Complete |
| MERGE-02 | Phase 1 | Complete |
| MERGE-03 | Phase 1 | Complete |
| MERGE-04 | Phase 1 | Complete |
| LIB-01 | Phase 2 | Complete |
| LIB-02 | Phase 2 | Complete |
| LIB-03 | Phase 2 | Complete |
| LIB-04 | Phase 2 | Complete |
| APP-01 | Phase 3 | Complete |
| APP-02 | Phase 3 | Complete |
| APP-03 | Phase 3 | Complete |
| APP-04 | Phase 3 | Complete |
| QA-01 | Phase 4 | Complete |
| QA-02 | Phase 4 | Complete |
| DOC-01 | Phase 4 | Complete |

**Coverage:**
- Milestone requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-30*
*Last updated: 2026-05-30 after roadmap creation*
