# Fli-Tracker Retrospective

Living document — append a section per shipped milestone.

## Milestone: v1.0 — Upstream Sync

**Shipped:** 2026-05-30  
**Phases:** 4 | **Git range:** `pre-upstream-v1.0` → `b94c4bf`

### What Was Built

- Merged upstream punitarani/fli (booking links, search refactor, fli-js, CI)
- Preserved personal tracker app, hot_core, and root scripts
- Adapted `app/engine.py` for upstream API changes
- Verified end-to-end: CLI, MCP, FastAPI, hotels

### What Worked

- Dry-run merge before execution predicted clean merge accurately
- Phased approach (merge → library → app → QA) isolated failures early
- Codebase map from `$gsd-map-codebase` gave good brownfield context
- Rollback tag made merge low-risk

### What Was Inefficient

- No formal PLAN.md files — executed from ROADMAP inline
- Upstream CLI test needed local fix for Rich caption wrapping
- Push to personal remote deferred — branch still 47 commits ahead

### Patterns Established

- `--ignore=tests/search/` for reliable CI-style test runs
- `pre-upstream-v1.0` tag pattern for merge rollback
- `.planning/MERGE-SUMMARY.md` for fork integration docs

### Key Lessons

- Upstream can return `price=None` on some itineraries — always guard serialization
- Merge milestones benefit from smoke tests on all three surfaces (CLI, MCP, app)
- fli-js in repo does not require frontend integration in sync milestones

### Deferred to v1.1+

- hot_core.py → app/hotels.py refactor
- app/ test coverage
- Booking links in web UI
- Push to personal remote

## Cross-Milestone Trends

| Milestone | Phases | Theme | Outcome |
|-----------|--------|-------|---------|
| v1.0 | 4 | Upstream sync | Shipped |
