# Milestones

## v1.0 Upstream Sync (Shipped: 2026-05-30)

**Phases:** 4 | **Requirements:** 15/15 complete

**Delivered:** Merged 31 upstream commits from punitarani/fli into personal fork at `flights` 0.10.0. Tracker app, CLI, MCP, and hotel search verified. Local customizations preserved.

**Key accomplishments:**

- Clean merge of `origin/main` with rollback tag `pre-upstream-v1.0`
- Fixed `app/engine.py` for upstream `FlightResult` entries with null prices
- Full app smoke test: FastAPI search, tracker CRUD, hotels API
- 433 tests passing, lint clean; merge documented in `MERGE-SUMMARY.md`

**Archives:**
- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)

**Git tag:** `v1.0`

---

## Pre-GSD History

Personal fork developed locally with:

- FastAPI tracker app (`app/`)
- Hotel search via `hot_core.py`
- Root-level trip planning scripts
- Fork point at upstream commit `1cb0231`
