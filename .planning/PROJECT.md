# Fli-Tracker

## What This Is

A personal fork of [punitarani/fli](https://github.com/punitarani/fli) — Python library for Google Flights (reverse-engineered API) at **v0.10.0** — extended with a FastAPI price-tracker web app (`app/`), hotel search, and local trip-planning scripts. Search via CLI, MCP, or browser UI; track prices in SQLite.

## Core Value

The personal tracker app and local workflows keep working while the underlying `fli` library stays current with upstream improvements (booking links, API fixes, CI).

## Current Milestone: v1.1 Fork Polish

**Goal:** Clean up fork-specific technical debt, add app test coverage, surface upstream booking deep-links in the web UI, and push the synced fork to the personal remote.

**Target features:**
- Move `hot_core.py` into `app/hotels.py` and remove the `sys.path` hack
- Archive superseded `flight_gui.py` and fix dependent imports
- Add `tests/app/` coverage for FastAPI routes and engine wrappers
- Expose per-flight `booking_url` in search API responses and web UI
- Push `main` (and milestone tag) to `personal` remote

## Current State (v1.0 shipped 2026-05-30)

**Shipped:** Upstream Sync — merged 31 commits from `punitarani/fli` without breaking the tracker app.

| Area | Status |
|------|--------|
| Upstream merge | ✅ `78866c5` — rollback tag `pre-upstream-v1.0` |
| Package version | `flights` 0.10.0 |
| Tracker app | ✅ Smoke-tested; no `booking_url` in API/UI yet |
| Tests | ✅ 433 passed (`--ignore=tests/search/`), zero `tests/app/` |
| Personal remote | ⚠️ ~48 commits ahead of `personal/main` |

See `.planning/milestones/v1.0-ROADMAP.md` and `.planning/MERGE-SUMMARY.md`.

## Requirements

### Validated

- ✓ Google Flights search via CLI — v0.10.0 with `booking_url`
- ✓ MCP server — expanded upstream tools
- ✓ FastAPI tracker app — flight/date/hotel search, tracker CRUD
- ✓ SQLite price tracking — background checks
- ✓ Merge upstream without losing tracker — v1.0
- ✓ Test suite green (excl. live API) — v1.0

### Active

See `.planning/REQUIREMENTS.md` for v1.1 milestone requirements.

### Out of Scope

- fli-js frontend integration — evaluate later, not this milestone
- Root script cleanup beyond `flight_gui.py` / `hot_core.py`
- PyPI/npm publishing — upstream process
- Deleting local JSON trip snapshots — user data

## Context

**Git remotes:**
- `origin` → upstream `punitarani/fli`
- `personal` → `larrycorsini/fli-tracker-personal.git`

**Repo includes:** `fli/` (Python), `fli-js/` (not integrated in UI), `app/` (tracker), local scripts.

## Constraints

- **Compatibility:** `app/engine.py` must keep working with `fli` search APIs
- **Data:** `app/data/tracker.db` stays gitignored
- **Testing:** Live `tests/search/` remain flaky in CI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge upstream into local main (not rebase) | Preserve history; easy rollback | ✓ Good — v1.0 |
| Keep `app/` as local layer | Personal tracker is the fork's purpose | ✓ Good |
| Skip fli-js in v1.0/v1.1 | Python app unchanged | Pending |
| Defer push until v1.1 | Ship polish before publishing fork | Pending — v1.1 goal |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

<details>
<summary>Prior milestones (archived)</summary>

**v1.0 Upstream Sync** (2026-05-30): Merged upstream, verified tracker. [Archive](milestones/v1.0-ROADMAP.md)

</details>

---
*Last updated: 2026-05-30 — v1.1 Fork Polish started*
