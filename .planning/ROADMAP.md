# Roadmap: Fli-Tracker

## Milestones

- ✅ **v1.0 Upstream Sync** — Phases 1–4 (shipped 2026-05-30) → [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Multi-Destination Tracker** — multi-dest-tracker (shipped 2026-06-18) → [archive](milestones/v1.1-ROADMAP.md)
- 📋 **Next milestone** — TBD via `$gsd-new-milestone` (likely Fork Polish tech debt: phases 5–8)

## Phases

<details>
<summary>✅ v1.0 Upstream Sync (Phases 1–4) — SHIPPED 2026-05-30</summary>

See [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

</details>

<details>
<summary>✅ v1.1 Multi-Destination Tracker — SHIPPED 2026-06-18</summary>

- [x] Multi-dest pipeline: `find_direct.py`, `tracker_config.py`, `alert.py`, `generate_flight_report.py`
- [x] Daily automation: `daily_flight_search.sh` + Netlify deploy
- [x] Static dashboard: `public/` (index, heatmap, history, PWA)
- [x] Live site: https://flights.larrycorsini.com

See [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) and [v1.1-phases/](milestones/v1.1-phases/).

</details>

## Backlog (deferred from v1.1 Fork Polish)

### Phase 5: Structural Cleanup

**Goal:** Relocate hotel search into the app package and remove legacy GUI cruft.  
**Requirements:** CLEAN-01, CLEAN-02, CLEAN-03

### Phase 6: App Test Coverage

**Goal:** Add reliable automated tests for the tracker app layer.  
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04

### Phase 7: Booking Links in FastAPI UI

**Goal:** Wire upstream booking deep-links through API and `app/static/app.js`.  
**Requirements:** FEAT-01, FEAT-02, FEAT-03

### Phase 8: Quality Gate

**Goal:** Lint, verify full suite.  
**Requirements:** QA-01

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1–4 | v1.0 | Complete | 2026-05-30 |
| multi-dest-tracker | v1.1 | Complete | 2026-06-18 |
| 5–8 Fork Polish | — | Backlog | — |

---
*Last updated: 2026-06-18 — v1.1 Multi-Destination Tracker shipped*
