# Fli-Tracker

## What This Is

A personal fork of [punitarani/fli](https://github.com/punitarani/fli) — Python library for Google Flights (reverse-engineered API) at **v0.10.0** — extended with a FastAPI price-tracker web app (`app/`), hotel search, and local trip-planning scripts. Search via CLI, MCP, or browser UI; track prices in SQLite.

## Core Value

The personal tracker app and local workflows keep working while the underlying `fli` library stays current with upstream improvements (booking links, API fixes, CI).

## Current State (v1.0 shipped 2026-05-30)

**Shipped:** Upstream Sync milestone — merged 31 commits from `punitarani/fli` without breaking the tracker app.

| Area | Status |
|------|--------|
| Upstream merge | ✅ `78866c5` — clean merge, rollback tag `pre-upstream-v1.0` |
| Package version | `flights` 0.10.0 |
| Tracker app (`app/`) | ✅ CLI, MCP, FastAPI, hotels verified |
| Tests | ✅ 433 passed (`--ignore=tests/search/`), lint clean |
| Personal remote push | Not done — 47 commits ahead of `personal/main` |

See `.planning/MERGE-SUMMARY.md` and `.planning/milestones/v1.0-ROADMAP.md` for full details.

## Next Milestone Goals

Candidate focus for v1.1 (not yet planned):

- Move `hot_core.py` into `app/hotels.py` (remove sys.path hack)
- Archive superseded `flight_gui.py`
- Add test coverage for `app/` module
- Surface booking deep-links in tracker web UI
- Push synced `main` to `personal` remote

Run `$gsd-new-milestone` to define scope.

## Requirements

### Validated

- ✓ Google Flights search via CLI — existing + upstream v0.10.0
- ✓ MCP server (`search_flights`, `search_dates`) — existing + expanded upstream
- ✓ FastAPI tracker app with flight/date/hotel search — v1.0 verified
- ✓ SQLite price tracking with background checks — v1.0 verified
- ✓ Shared `fli/core/` parsing used by CLI and MCP — existing
- ✓ Rate-limited HTTP client with retries — existing
- ✓ Merge upstream without losing tracker — v1.0
- ✓ Upstream booking deep-links in Python library — v1.0
- ✓ Test suite green (excl. live API) — v1.0

### Active

(None — define in next milestone via `$gsd-new-milestone`)

### Out of Scope

- fli-js frontend integration — defer to v1.1+ evaluation
- Root script cleanup — separate cleanup milestone
- Full `app/` test suite — deferred from v1.0
- PyPI/npm publishing — upstream process
- Deleting local JSON trip snapshots — user data

## Context

**Git remotes:**
- `origin` → upstream `punitarani/fli`
- `personal` → `larrycorsini/fli-tracker-personal.git`

**Repo now includes:** `fli/` (Python), `fli-js/` (TypeScript, not integrated in UI), `app/` (tracker), local scripts.

## Constraints

- **Compatibility:** `app/engine.py` must keep working with `fli` search APIs
- **Data:** `app/data/tracker.db` stays gitignored (local SQLite)
- **Testing:** Live `tests/search/` API tests remain flaky in CI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge upstream into local main (not rebase) | Preserve history; easy rollback | ✓ Good — tag `pre-upstream-v1.0` |
| Keep `app/` as local layer | Personal tracker is the fork's purpose | ✓ Good — all smoke tests pass |
| Skip fli-js integration in v1.0 | TS port new; Python app unchanged | ✓ Good — deferred to v1.1 |
| Skip push to `personal` in v1.0 | Optional; user-controlled | ⚠️ Revisit — still 47 commits ahead |

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
<summary>v1.0 milestone planning context (archived)</summary>

Initial milestone goal: merge latest upstream without breaking tracker app, scripts, or customizations. Completed 2026-05-30 across 4 phases. Full roadmap: `.planning/milestones/v1.0-ROADMAP.md`.

</details>

---
*Last updated: 2026-05-30 after v1.0 milestone completion*
