# Roadmap: Fli-Tracker

## Milestones

- ✅ **v1.0 Upstream Sync** — Phases 1–4 (shipped 2026-05-30) → [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Fork Polish** — Phases 5–8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Upstream Sync (Phases 1–4) — SHIPPED 2026-05-30</summary>

See [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

</details>

### Phase 5: Structural Cleanup

**Goal:** Relocate hotel search into the app package and remove legacy GUI cruft.

**Depends on:** Nothing (first phase of v1.1)

**Requirements:** CLEAN-01, CLEAN-02, CLEAN-03

**Success Criteria:**
1. `app/hotels.py` contains former `hot_core.py` logic; root `hot_core.py` removed
2. `app/engine.py` has no `sys.path` manipulation
3. `flight_gui.py` archived; hotel/flight smoke paths still import correctly
4. `uv run pytest -vv --ignore=tests/search/` still passes after refactor

**Plans:** TBD via `$gsd-plan-phase 5`

---

### Phase 6: App Test Coverage

**Goal:** Add reliable automated tests for the tracker app layer.

**Depends on:** Phase 5 (clean import paths)

**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04

**Success Criteria:**
1. `tests/app/` covers server routes, engine serialization, and hotel wrapper
2. Null-price flight regression test exists (v1.0 merge fix)
3. Hotel tests use mocks — no live API in CI
4. Full non-search test suite passes including new app tests

**Plans:** TBD via `$gsd-plan-phase 6`

---

### Phase 7: Booking Links in UI

**Goal:** Wire upstream booking deep-links through API and web UI.

**Depends on:** Phase 6 (tests guard regressions)

**Requirements:** FEAT-01, FEAT-02, FEAT-03

**Success Criteria:**
1. `/api/search/flights` SSE/JSON payloads include `booking_url` per flight
2. `/api/search/dates` includes `booking_url` per date row
3. Flight and date result cards in `app/static/app.js` link to Google Flights
4. Combined trip cards use real flight booking URLs (not placeholder `#`)

**Plans:** TBD via `$gsd-plan-phase 7`

---

### Phase 8: Quality Gate & Push

**Goal:** Lint, verify full suite, publish fork to personal remote.

**Depends on:** Phase 7

**Requirements:** QA-01, PUSH-01

**Success Criteria:**
1. `make lint` clean
2. `uv run pytest -vv --ignore=tests/search/` passes
3. `git push personal main` succeeds
4. Annotated tag `v1.1` pushed to `personal`

**Plans:** TBD via `$gsd-plan-phase 8`

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1–4 | v1.0 | 6/6 | Complete | 2026-05-30 |
| 5. Structural Cleanup | v1.1 | 0/? | Not started | — |
| 6. App Test Coverage | v1.1 | 0/? | Not started | — |
| 7. Booking Links in UI | v1.1 | 0/? | Not started | — |
| 8. Quality Gate & Push | v1.1 | 0/? | Not started | — |

---
*Last updated: 2026-05-30 — v1.1 roadmap created*
