# Fli-Tracker

## What This Is

A personal fork of [punitarani/fli](https://github.com/punitarani/fli) — a Python library for Google Flights via reverse-engineered API — extended with a FastAPI price-tracker web app (`app/`), hotel search integration, and local automation scripts. Used for tracking flight prices, planning trips, and searching flights through CLI, MCP, and browser UI.

## Core Value

The personal tracker app and local workflows keep working while the underlying `fli` library stays current with upstream improvements (booking links, API fixes, CI).

## Current Milestone: v1.0 Upstream Sync

**Goal:** Merge latest upstream `punitarani/fli` (31 commits since merge-base) without breaking the tracker app, scripts, or local customizations.

**Target features:**
- Merge `origin/main` into local `main` cleanly
- Preserve all local-only code: `app/`, `hot_core.py`, root scripts, tracker data patterns
- Adopt upstream Python improvements (booking deep-links, core refactors, dependency updates)
- Verify CLI, MCP, and web app still work after merge
- Document what changed and what stayed local

## Requirements

### Validated

- ✓ Google Flights search via CLI (`fli flights`, `fli dates`) — existing
- ✓ MCP server with `search_flights` and `search_dates` — existing
- ✓ FastAPI web app with flight/date/hotel search and price tracker — existing (`app/`)
- ✓ SQLite-backed flight price tracking with background checks — existing (`app/tracker.py`)
- ✓ Shared parsing/builders in `fli/core/` used by CLI and MCP — existing
- ✓ Rate-limited HTTP client with retries — existing (`fli/search/client.py`)

### Active

- [ ] Merge upstream without losing local tracker functionality
- [ ] Resolve any merge conflicts preserving local app customizations
- [ ] Update `app/engine.py` if upstream API/model changes require it
- [ ] Run full test suite (excluding flaky live API tests) green after merge
- [ ] Smoke-test web app: search, track flight, price check
- [ ] Record merge decisions and upstream features adopted

### Out of Scope

- Adopting the new TypeScript `fli-js` package into the web frontend — separate effort; merge brings it into repo but no integration required this milestone
- Deleting root-level personal scripts (`flight_gui.py`, etc.) — deferred to cleanup milestone
- Adding test coverage for entire `app/` module — deferred
- Publishing to PyPI or npm — upstream concern only

## Context

**Git remotes:**
- `origin` → `https://github.com/punitarani/fli` (upstream)
- `personal` → `https://github.com/larrycorsini/fli-tracker-personal.git` (personal remote)

**Divergence (as of 2026-05-30):**
- Local `main` is **14 commits ahead**, **31 commits behind** `origin/main`
- Merge-base: `1cb0231`
- Dry-run merge: **clean auto-merge** on `pyproject.toml` and `uv.lock` (no conflicts detected)
- Local-only additions: `app/` (676+ lines engine, server, tracker, static UI), `hot_core.py`, root scripts, JSON trip snapshots

**Upstream highlights since fork:**
- TypeScript/JS port (`packages/fli-js/`)
- Per-flight booking deep-link URLs (`fli/core/links.py`, protobuf encoding)
- Search module refactor (`_proto`, `_wire`, `_decoders`, `_urls`)
- CI/release fixes, docs reorganization

**Recent local fixes (already on main):**
- F-01–F-05 audit fixes: fuzz marker, asyncio deprecation, uv paths, playwright removed, `*.db` gitignored

## Constraints

- **Compatibility:** `app/engine.py` must continue calling `fli` search APIs without regression
- **Dependencies:** Keep local `pyproject.toml` extras that support the web app (FastAPI, etc.)
- **Data:** Do not re-commit `app/data/tracker.db`; user SQLite stays local
- **Testing:** Skip `tests/search/` live API tests in CI verification (rate-limited/flaky per AGENTS.md)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge upstream into local main (not rebase) | Preserves local commit history; easier rollback | — Pending |
| Keep `app/` as local layer on top of `fli` | Personal tracker is the reason for the fork | — Pending |
| Skip fli-js integration this milestone | TS port is new upstream surface; Python app unchanged | — Pending |
| Push to `personal` remote after verification | `origin` is read-only upstream | — Pending |

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

---
*Last updated: 2026-05-30 after milestone v1.0 initialization*
