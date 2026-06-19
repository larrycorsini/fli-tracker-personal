<!-- generated-by: gsd-doc-writer -->
---
phase: multi-dest-tracker
phase_name: "Multi-Destination Tracker"
project: "Fli-Tracker"
generated: "2026-06-18"
counts:
  decisions: 8
  lessons: 7
  patterns: 5
  surprises: 4
missing_artifacts:
  - "*-PLAN.md"
  - "*-SUMMARY.md"
  - "*-VERIFICATION.md"
---

# Phase multi-dest-tracker Learnings: Multi-Destination Tracker

## Decisions

### Two-phase search pipeline (SearchDates → SearchFlights)

Phase 1 uses `SearchDates` to shortlist cheap date pairs; phase 2 runs `SearchFlights` on the shortlist for times, airlines, and per-itinerary `booking_url` deep links.

**Rationale:** Mirrors Google Flights price-graph behavior while keeping API quota manageable across 8 regions × multiple origins.
**Source:** REVIEW.md, RETROSPECTIVE.md, find_direct.py

---

### Static Netlify dashboard instead of FastAPI UI for booking links

Shipped generated HTML (`public/index.html`, `heatmap.html`, `history.html`) with embedded Google Flights booking URLs rather than wiring booking links through the FastAPI tracker app.

**Rationale:** Reusing upstream `booking_url` in generated HTML delivered a public product faster than extending the live app UI.
**Source:** RETROSPECTIVE.md

---

### Centralized region config in `tracker_config.py`

All 8 destination regions, alert thresholds, excluded budget carriers, and two-phase search constants live in one shared module consumed by search, report, and alert scripts.

**Rationale:** Single source of truth makes adding destinations and tuning thresholds a one-file change.
**Source:** RETROSPECTIVE.md, REVIEW.md

---

### `FLI_ALERT_PHONE` environment variable for iMessage alerts

Removed hardcoded default phone from `alert.py`; alerts require `FLI_ALERT_PHONE` set in the launchd plist (or environment). Missing var skips alerts gracefully (non-fatal in daily pipeline).

**Rationale:** Prevents personal phone numbers in git history and misdirected alerts on cloned repos.
**Source:** REVIEW.md (CR-02)

---

### Daily pipeline uses `find_direct.py --force`

The launchd job passes `--force` so every morning re-searches all regions instead of resuming stale checkpoint data.

**Rationale:** Resume logic skips any region with non-empty cached flights; without `--force`, prices and booking URLs go stale across days.
**Source:** REVIEW.md (WR-01), daily_flight_search.sh

---

### Google Flights–inspired UX with locked brand tokens

UI contract targets primary `#1F2A37`, accent `#1A73E8`, Roboto typography, mobile-first layout, booking deep-link on every fare, and weekday abbreviations beside dates.

**Rationale:** User preference for familiar Google Flights scan patterns and consistent brand identity across static pages.
**Source:** UI-SPEC.md, AGENTS.md

---

### Show empty regions rather than hiding tabs

Regions with no fares (e.g. Cancun) keep a visible tab and display an empty-state message instead of removing the destination from the UI.

**Rationale:** Deal board and navigation stay stable; users see that a region is monitored even when no fares match filters.
**Source:** multi-dest-UAT.md (test 8), UI-SPEC.md

---

### Exclude budget/low-cost carriers from searches

Frontier (F9), Breeze (MX), Spirit (NK), Allegiant (G4), Sun Country (SY), and Avelo (XP) are filtered at search time via shared config.

**Rationale:** Aligns recommendations with Chase Sapphire Preferred redemption quality and user travel preferences.
**Source:** tracker_config.py (referenced in REVIEW.md), AGENTS.md

---

## Lessons

### Resume semantics without `--force` produce stale daily data

Checkpoint JSON causes `find_direct.py` to skip any region that already has flights, so a daily run without `--force` never refreshes completed regions.

**Context:** Discovered during code review of daily automation; fixed by adding `--force` to `daily_flight_search.sh`.
**Source:** REVIEW.md (WR-01)

---

### Embedding `json.dumps` output in Alpine `x-data` double-quoted attributes breaks HTML

Double-quoted JSON inside `x-data="..."` terminates the attribute early, breaking `intlTabs` on index and `heatmapData` on heatmap pages.

**Context:** Verified in deployed `public/index.html` and `public/heatmap.html` generated output.
**Source:** REVIEW.md (CR-01)

---

### Partial search failures can block the entire deploy pipeline

`find_direct.py` returns exit code 1 when `_stats["errors"] > 0`, and `daily_flight_search.sh` treats non-zero as fatal — skipping report generation and Netlify deploy even when partial results exist in `best_direct.json`.

**Context:** Multi-region runs may succeed for most regions while one API call fails.
**Source:** REVIEW.md (WR-03)

---

### Scratch files at repo root pollute pytest collection

Ad-hoc JSON and test scripts left in the project root broke test discovery and created planning drift when the milestone executed without formal PLAN/SUMMARY artifacts.

**Context:** v1.1 shipped ad hoc after rescoping from Fork Polish; cleanup deferred to next milestone.
**Source:** RETROSPECTIVE.md

---

### Static UAT auto-verification covers structure but not interaction

10 of 19 UAT scenarios passed via static HTML/JSON analysis (tabs, booking URL counts, empty states); 9 interactive scenarios (tab switching, filters, book links, heatmap/history charts) remain pending manual browser verification.

**Context:** Browser MCP unavailable during UAT; structural checks caught most regressions early.
**Source:** multi-dest-UAT.md

---

### UI-SPEC palette migration lagged behind shipped generator output

UI-SPEC locked `#1F2A37` + `#1A73E8` Google blue, but deployed generator still used legacy purple (`#BD8BCA`) at spec time; partial rebrand applied teal accent (`#14B8A6`) per UI-REVIEW session work.

**Context:** Design contract and generator output diverged; full migration deferred to next milestone.
**Source:** UI-SPEC.md (FLAG-01), multi-dest-UI-REVIEW.md, RETROSPECTIVE.md

---

### Non-atomic writes for HTML reports and alert state risk truncated deploys

Unlike `find_direct.py` checkpoint JSON (atomic write), `generate_flight_report.py` and `alert.py` write HTML and `last_alert.json` directly — a crash mid-write can leave truncated files for Netlify deploy.

**Context:** Identified in code review; fix deferred (reuse atomic write helper).
**Source:** REVIEW.md (WR-04)

---

## Patterns

### Search → JSON → Report → Deploy pipeline

`find_direct.py` writes `best_direct.json` → `generate_flight_report.py` emits `public/*.html` → `npx netlify-cli deploy --prod --dir=public`. Optional `alert.py` runs between search and report when `FLI_ALERT_PHONE` is set.

**When to use:** Any daily or manual refresh of the static flight dashboard.
**Source:** RETROSPECTIVE.md, daily_flight_search.sh

---

### Per-region atomic checkpointing during long searches

`find_direct.py` calls `atomic_write_json(OUTPUT_JSON, all_results)` after each region completes phase 2, so interrupted multi-hour runs resume from the last finished region.

**When to use:** Long-running multi-destination API searches where total runtime exceeds failure tolerance.
**Source:** REVIEW.md, find_direct.py

---

### Price-`None` guards before sort/min operations

Filter flights with `price is not None` before `min()`, sort, or serialization — mirrors `app/engine.py` and prevents crashes on upstream unpriced rows.

**When to use:** Any code path sorting or alerting on `FlightResult`-derived dicts.
**Source:** REVIEW.md, alert.py `_priced_flights`

---

### UAT auto-verification from generated artifacts

Validate tab counts, booking URL presence, weekday abbreviations, and regional flight counts by grepping `public/*.html` and `best_direct.json` without a live browser.

**When to use:** CI-style regression checks on static generator output before manual interaction testing.
**Source:** multi-dest-UAT.md

---

### Non-fatal alert step in orchestration shell script

`daily_flight_search.sh` runs `alert.py` with `|| echo "WARN: ..."` so iMessage failures never block report generation or Netlify deploy.

**When to use:** Optional notification steps in automated pipelines where core deliverable is the static site update.
**Source:** daily_flight_search.sh, REVIEW.md

---

## Surprises

### Cancun region returns zero fares but must remain in UI

Search pipeline produces an empty list for Cancun while other regions have hundreds of flights; UAT confirmed the tab renders "No flights found for Cancun." without layout breakage.

**Impact:** Validates empty-state pattern is essential — hiding the tab would confuse deal-board expectations.
**Source:** multi-dest-UAT.md (test 8)

---

### Europe region data volume dwarfs domestic regions

`best_direct.json` contained 866 Europe flights vs. 184 DFW at UAT time — report generation and HTML size scale significantly with international shortlists.

**Impact:** Heatmap inlines full JSON in Alpine state; large payloads exacerbate CR-01 x-data breakage on heatmap page.
**Source:** multi-dest-UAT.md (test 3)

---

### Milestone rescoped mid-roadmap from Fork Polish to multi-dest delivery

Original v1.1 plan (phases 5–8: hot_core refactor, app tests, FastAPI booking links) was deferred; a single multi-dest phase shipped the public Netlify product instead.

**Impact:** Shipped usable dashboard faster but accumulated tech debt (no PLAN.md, scratch files, deferred lint gate).
**Source:** RETROSPECTIVE.md, STATE.md

---

### Accent color diverged between UI-SPEC and rebrand implementation

UI-SPEC specified Google blue `#1A73E8`; session rebrand applied teal `#14B8A6` as accent in generator CSS variables — both depart from legacy purple but are inconsistent with each other.

**Impact:** Future palette work must pick one accent standard before full UI-SPEC migration.
**Source:** UI-SPEC.md, multi-dest-UI-REVIEW.md (Palette Applied table)
