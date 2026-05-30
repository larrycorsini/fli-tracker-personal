# Roadmap: Fli-Tracker — Milestone v1.0 Upstream Sync

## Overview

Merge 31 upstream commits from punitarani/fli into the personal fork, preserve the tracker app and local customizations, adapt any broken integrations, and verify everything works before pushing to the personal remote.

## Phases

- [x] **Phase 1: Baseline & Merge** — Tag pre-merge state, merge upstream, resolve conflicts
- [x] **Phase 2: Library Verification** — Confirm CLI, MCP, and engine wrappers work with merged `fli`
- [x] **Phase 3: App Smoke Test** — Verify FastAPI tracker, search, and hotel endpoints
- [x] **Phase 4: Quality Gate & Ship** — Lint, tests, merge documentation, push to personal remote

## Phase Details

### Phase 1: Baseline & Merge
**Goal**: Safely integrate upstream `origin/main` into local `main`
**Depends on**: Nothing (first phase)
**Requirements**: MERGE-01, MERGE-02, MERGE-03, MERGE-04
**Success Criteria** (what must be TRUE):
  1. Pre-merge baseline recorded (git tag or documented commit SHA)
  2. `git merge origin/main` completes with all conflicts resolved
  3. `app/`, `hot_core.py`, and local scripts still exist in working tree
  4. `uv sync --all-extras` succeeds with merged lockfile
**Plans**: 2 plans

Plans:
- [x] 01-01: Record baseline, fetch upstream, dry-run merge analysis
- [x] 01-02: Execute merge, resolve conflicts (expect clean auto-merge on pyproject.toml/uv.lock), sync deps

### Phase 2: Library Verification
**Goal**: Confirm merged `fli` package works for all entry points
**Depends on**: Phase 1
**Requirements**: LIB-01, LIB-02, LIB-03, LIB-04
**Success Criteria** (what must be TRUE):
  1. `uv run fli flights` returns JSON results for a known route
  2. MCP server imports and lists tools without error
  3. `app/engine.py` search functions execute without ImportError or API mismatch
  4. New upstream modules (`fli/core/links.py`, search helpers) are importable
**Plans**: 2 plans

Plans:
- [x] 02-01: Smoke-test CLI and MCP after merge
- [x] 02-02: Fix any `app/engine.py` breakages from upstream API changes

### Phase 3: App Smoke Test
**Goal**: Verify the personal tracker web app still works end-to-end
**Depends on**: Phase 2
**Requirements**: APP-01, APP-02, APP-03, APP-04
**Success Criteria** (what must be TRUE):
  1. `uvicorn app.server:app` starts on port 8000
  2. Flight search via API returns structured results
  3. Tracker add/list/check endpoints respond correctly
  4. Hotel search endpoint returns results (hot_core integration intact)
**Plans**: 1 plan

Plans:
- [x] 03-01: Manual or scripted smoke test of all `/api/*` routes

### Phase 4: Quality Gate & Ship
**Goal**: Pass automated checks and document the merge for future reference
**Depends on**: Phase 3
**Requirements**: QA-01, QA-02, DOC-01
**Success Criteria** (what must be TRUE):
  1. `pytest --ignore=tests/search/` all green
  2. `make lint` passes
  3. Merge summary documents upstream features adopted and any local adaptations
  4. Changes pushed to `personal` remote (optional, user-approved)
**Plans**: 1 plan

Plans:
- [x] 04-01: Run lint + tests, write merge notes, commit and optionally push

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Baseline & Merge | 2/2 | Complete | 2026-05-30 |
| 2. Library Verification | 2/2 | Complete | 2026-05-30 |
| 3. App Smoke Test | 1/1 | Complete | 2026-05-30 |
| 4. Quality Gate & Ship | 1/1 | Complete | 2026-05-30 |

---
*Roadmap created: 2026-05-30*
*Milestone: v1.0 Upstream Sync*
