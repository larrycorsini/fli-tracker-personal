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

## Milestone: v1.1 — Multi-Destination Tracker

**Shipped:** 2026-06-18  
**Phase:** multi-dest-tracker | **Git tag:** v1.1

### What Was Built

- Two-phase search pipeline (`find_direct.py`) across 8 regions from SLC/PVU
- Static Netlify dashboard with booking deep-links (index, heatmap, history)
- Daily automation (`daily_flight_search.sh`) and iMessage price alerts
- Shared config (`tracker_config.py`) with excluded budget carriers

### What Worked

- Rescoping v1.1 from Fork Polish to pipeline delivery shipped a usable public product
- Reusing upstream `booking_url` in generated HTML avoided FastAPI UI work
- UAT auto-verification caught 10/11 scenarios from static file analysis
- `tracker_config.py` centralizes regions — easy to add destinations

### What Was Inefficient

- Original Fork Polish roadmap (phases 5–8) planned but never executed — created planning drift
- No formal PLAN.md/SUMMARY.md for multi-dest phase — executed ad hoc
- Scratch scripts (`test_heatmap.py`, root JSON) accumulated and broke pytest collection
- UI palette still legacy purple; UI-SPEC target not applied in generator

### Patterns Established

- Pipeline: `find_direct.py` → `best_direct.json` → `generate_flight_report.py` → `public/`
- `daily_flight_search.sh` orchestrates search, alert, report, Netlify deploy
- `.gitignore` excludes runtime JSON and scratch scripts from commits
- Netlify static publish with security headers in `netlify.toml`

### Key Lessons

- Milestone rescoping is valid when user priority shifts — document deferred scope explicitly
- Scratch files at repo root need gitignore rules or they pollute pytest collection
- Static generated site can deliver booking links faster than wiring FastAPI UI

### Deferred to Next Milestone

- Fork Polish: hot_core refactor, tests/app, FastAPI booking links, lint gate
- UI-SPEC palette migration in generator
- Live UAT scenario #1 (production URL manual check)

## Cross-Milestone Trends

| Milestone | Phases | Theme | Outcome |
|-----------|--------|-------|---------|
| v1.0 | 4 | Upstream sync | Shipped |
| v1.1 | 1 | Multi-dest tracker | Shipped |
