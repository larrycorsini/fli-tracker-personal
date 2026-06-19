# Phase multi-dest-tracker — UI Review

**Audited:** 2026-06-18  
**Baseline:** `.planning/phases/multi-dest-tracker/UI-SPEC.md`  
**Screenshots:** not captured (no local dev server; code + generator audit)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Spec CTAs, empty/filtered copy, weekday dates via `format_date` |
| 2. Visuals | 3/4 | Strong hierarchy; 3.7MB index HTML hurts perceived performance |
| 3. Color | 4/4 | Full `#1F2A37` + `#1A73E8` migration; zero purple in `public/` |
| 4. Typography | 3/4 | Roboto 400/500/700; mixed Tailwind `text-gray-*` with CSS vars |
| 5. Spacing | 3/4 | 44px targets, tab-fade on all pages; fare cards dense on mobile |
| 6. Experience Design | 3/4 | Skip links, ARIA tabs, keyboard expand; no static error page for missing JSON |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **Index HTML payload (~3.7MB)** — Slow first paint on mobile — Split fare data to external JSON or paginate regions (deferred; not blocking deploy).
2. **Mixed color sources (`text-gray-500` vs `--text-secondary`)** — Minor inconsistency if tokens change — Map Tailwind grays to CSS vars in a future pass.
3. **Global heatmap thresholds ($320/$500)** — Misleading colors for Europe/Japan — Per-region tier config in `tracker_config.py` (INFO-01).

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

- **PASS:** Hero CTA `View flight options`, booking `Select flight`, Chase `Go to Chase Travel` (`generate_flight_report.py`).
- **PASS:** Empty region includes `~6 AM` guidance.
- **PASS:** Filter empty: `No fares match your filters. Widen max price or choose All Airlines.`
- **PASS:** Heatmap/history empty strings match contract.
- **WARNING:** Disabled deal pill uses em dash `—` without explicit "No fares" text — mitigated by `title` tooltip.

### Pillar 2: Visuals (3/4)

- **PASS:** Hero aviation photo + gradient preserved.
- **PASS:** Deal board shows all 8 regions; Cancun disabled pill when empty.
- **PASS:** Shared nav/footer via `get_nav_*()` helpers.
- **WARNING:** `public/index.html` is very large — visual polish undermined by load time on slow networks.

### Pillar 3: Color (4/4)

- **PASS:** `:root` defines full token set including `--success`, `--warning`, heatmap tiers.
- **PASS:** `grep` confirms no `#BD8BCA` or `purple` in `public/*.html`.
- **PASS:** Heatmap mid tier uses `#111827` text on `#F9AB00` (WCAG).
- **PASS:** `manifest.json` `theme_color`: `#1F2A37`.

### Pillar 4: Typography (3/4)

- **PASS:** Roboto from Google Fonts; hero 40/48px, prices 32px/500.
- **WARNING:** Body copy still uses Tailwind `text-gray-500/700/800` instead of `--text-secondary` / `--text-primary` exclusively.
- **PASS:** Uppercase labels use 12px / tracking-wider pattern.

### Pillar 5: Spacing (3/4)

- **PASS:** `tab-btn` min-height 44px; `deal-chip` min-height 44px; nav links min-h-[44px].
- **PASS:** `tab-fade` + `tab-scroll` on index, heatmap, history.
- **PASS:** `overflow-x-hidden` on body.
- **WARNING:** Fare list padding `p-6 md:p-8` is generous on small screens — acceptable per Google Flights density spec.

### Pillar 6: Experience Design (3/4)

- **PASS:** Skip links on all three pages (`#flights`, `#main-content`).
- **PASS:** `role="tablist"` / `aria-selected` on index, heatmap, history.
- **PASS:** Fare rows use `<button>` with `aria-expanded` / `aria-controls`.
- **PASS:** Heatmap cells link to `flight.url` when available.
- **PASS:** `prefers-reduced-motion` for chevron.
- **WARNING:** No user-facing error if `best_direct.json` missing (generator prints to stdout only).
- **INFO:** Filter-empty state uses inline JSON in `x-show` — works but bloats HTML.

---

## Page-Specific Notes

### index.html

- 8 region tabs always rendered via `REGIONS.keys()`.
- Deal board: 7 active chips + 1 disabled (Cancun) in current data.
- Best-value box and booking URLs on every time option.

### heatmap.html

- Region tabs + booking-linked cells.
- Empty panel: `No data for this region yet.`
- Skip link → `#main-content`.

### history.html

- Chart stroke `#1A73E8`; empty overlay when no labels.
- Shared nav with heatmap + flights links.

---

## Registry Safety

Registry audit: shadcn not initialized — **skipped** (N/A).

---

## Files Audited

- `generate_flight_report.py`
- `public/index.html`
- `public/heatmap.html`
- `public/history.html`
- `public/manifest.json`
- `.planning/phases/multi-dest-tracker/UI-SPEC.md`
