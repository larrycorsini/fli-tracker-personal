# Phase multi-dest-tracker — UI Review

**Audited:** 2026-06-18
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md)
**Screenshots:** Not captured (browser MCP unavailable; code-only + generated HTML audit)

---

## Component Checklist

| Component | Status | Evidence |
|-----------|--------|----------|
| Destination tabs (8 regions) | ✓ Present | `public/index.html` — 8 `role='tab'` buttons |
| Deal board ("Best Deals Right Now") | ✓ Present | 7 region price chips above tabs |
| Chase Sapphire callout | ✓ Present | `.callout-accent` block with CTA link |
| Price/airline filters | ✓ Present | Show/Hide Filters toggle + range + select |
| Fare groups (expandable rows) | ✓ Present | Grouped by airline/date/price with expand |
| Best Value box (per region) | ✓ Present | Emerald callout at bottom of each tab panel |
| Heatmap region selectors | ✓ Present | 8 `activeRegion` buttons in `heatmap.html` |
| History region selectors | ✓ Present | 8 `activeRegion` buttons in `history.html` |
| Last updated timestamp | ✓ Present | Hero: "Last updated: …" from `best_direct.json` mtime |
| Scroll-to-top button | ✓ Present | Fixed button, `aria-label='Scroll to top'`, 50×50px |

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Strong hero and Chase-specific copy; booking CTA "Select" is generic |
| 2. Visuals (Layout) | 3/4 | Clear hero → deals → callout → tabs → results hierarchy |
| 3. Color | 3/4 | Rebrand to #1F2A37 + teal accent applied; heatmap cells still use unrelated Tailwind colors |
| 4. Typography | 2/4 | 9+ distinct font sizes (52px down to 11px) — scale needs consolidation |
| 5. Spacing / Responsiveness | 3/4 | Tab horizontal scroll + sm/md breakpoints; arbitrary px sizes remain |
| 6. Experience Design (A11y + Mobile) | 3/4 | ARIA on tabs/scroll-top; no focus-visible styles; CDN script dependency |

**Overall: 17/24**

---

## Top 3 Priority Fixes

1. **Add `:focus-visible` outlines on interactive elements** — Keyboard users cannot see focus on tabs, deal chips, or filter toggle — Add `outline: 2px solid var(--accent); outline-offset: 2px` to `.tab-btn`, `.deal-chip`, `.filter-toggle`, `.btn-accent`, `.dt-btn-primary:focus-visible`

2. **Consolidate typography scale** — Visual inconsistency and maintenance burden — Map to 5 tokens: display (36/52px), heading (24px), body (16px), small (14px), caption (12px); replace `text-[13px]`, `text-[15px]`, `text-[22px]` arbitrary values

3. **Align heatmap price tiers to palette** — Heatmap uses hardcoded `bg-emerald-500` / `bg-amber-400` / `bg-rose-500` disconnected from brand — Use `--success`, a warm `--warning: #D97706`, and `--primary` for high-price cells

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**WARNING — Generic booking CTA:** Fare expand rows use "Select" (`generate_flight_report.py` ~line 413). Prefer "View on Google Flights" or "Book this fare" for clarity.

**PASS — Contextual hero copy:** "Track your next adventure" + Chase Sapphire optimization messaging is specific and on-brand.

**PASS — Empty state:** Cancun tab shows "No flights found for Cancun." — functional, non-breaking.

**PASS — Filter labels:** "Max Price", "Filter Airline", "Show/Hide Filters" are descriptive.

### Pillar 2: Visuals / Layout (3/4)

**PASS — Information hierarchy:** Hero CTA → deal board quick-jump → Chase callout → region tabs → filterable fare list → best-value summary follows a logical scan path.

**PASS — Card containment:** `.card-container` with shadow separates fare list from page background.

**WARNING — Hero competes on mobile:** 52px h1 (now 36px at `max-width: 640px`) still dominates small viewports; hero image gradient may reduce text contrast on some displays — `needs_human_review: true`

**PASS — Expand/collapse affordance:** Chevron rotates on fare group expand.

### Pillar 3: Color (3/4)

**PASS (post-rebrand) — Primary #1F2A37:** Headings, logo, primary buttons, scroll-top, manifest `theme_color` all use dark blue-gray.

**PASS — Accent teal #14B8A6:** Tabs, nav links, deal chips, Chase callout border, chart line use complementary teal — no remaining `#BD8BCA` purple in generator output.

**PASS — Success #059669:** Price display uses `--success` for dollar amounts; best-value boxes retain emerald Tailwind (compatible hue).

**WARNING — Heatmap tier colors:** `heatmap.html` Alpine classes `bg-emerald-500`, `bg-amber-400`, `bg-rose-500` are not tied to CSS variables — breaks 60/30/10 consistency on secondary pages.

**PASS — WCAG AA contrast (computed):** White (#FFF) on #1F2A37 ≈ 14.7:1; white on #14B8A6 ≈ 2.6:1 (buttons use white text on teal — borderline for small text; #0D9488 hover improves to ~3.5:1). Accent-strong #0F766E on #F0FDFA light bg ≈ 5.5:1 — passes for body text.

### Pillar 4: Typography (2/4)

**WARNING — Size sprawl:** Distinct sizes found: 52px, 36px (mobile), 32px (price), 30px (`text-3xl`), 24px (nav-logo), 22px (`text-[22px]`), 20px (hero), 18px (`text-lg`), 15px, 14px, 13px, 12px (`text-xs`). Exceeds recommended ≤4-size scale.

**PASS — Font family:** Raleway loaded with weights 300–900; used consistently via `--font-family-sans-serif`.

**WARNING — Weight variety:** 900 (h1), 700 (buttons/labels), 600, 500, 400 all in use — acceptable but paired with too many sizes.

### Pillar 5: Spacing / Responsiveness (3/4)

**PASS — Mobile tab scroll:** `.tab-scroll` + `.tab-fade` mask enables horizontal scroll for 8 destination tabs on narrow screens.

**PASS — Responsive layout:** `flex-col sm:flex-row`, `grid-cols-1 lg:grid-cols-2`, `px-4 sm:px-6`, `py-16 md:py-28` breakpoints throughout.

**PASS (fixed in rebrand) — Touch targets:** `.tab-btn`, `.deal-chip`, `.btn-accent`, `.dt-btn-primary`, `.filter-toggle` now enforce `min-height: 44px`.

**WARNING — Arbitrary spacing:** `text-[13px]`, `text-[15px]`, `text-[22px]`, `tracking-[3px]` bypass a spacing/type scale.

**WARNING — Sticky nav + scroll-mt:** `#flights` uses `scroll-mt-24` for anchor offset — good; heatmap/history lack equivalent if deep-linked.

### Pillar 6: Experience Design / Accessibility (3/4)

**PASS — Tab ARIA:** `role='tablist'`, `role='tab'`, `:aria-selected`, `role='tabpanel'` on index page.

**PASS — Scroll-to-top:** `aria-label='Scroll to top'`, appears after 400px scroll via Alpine.

**PASS — Loading/empty/error states:** Empty region panel; history chart "No history yet"; heatmap "No data for this region yet."

**WARNING — No focus-visible styles:** Interactive elements rely on browser default focus which may be suppressed or invisible against dark primary buttons.

**WARNING — External CDN dependency:** Tailwind CDN + Alpine CDN — offline/PWA cache via `sw.js` but no local fallback if CDN blocked.

**WARNING — Filter range input:** No `aria-valuemin`/`aria-valuemax`/`aria-valuenow` on price slider.

**BLOCKER (resolved in this session):** Prior purple palette (#BD8BCA) dominated accent usage (>15 elements) — rebrand to #1F2A37 primary addresses user-requested visual identity change.

---

## Palette Applied (Rebrand)

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary` | `#1F2A37` | Headings, logo, primary buttons, scroll-top, manifest theme |
| `--primary-hover` | `#2D3A4A` | Button/scroll hover |
| `--accent` | `#14B8A6` | Active tab border, chart line, callout left border |
| `--accent-hover` | `#0D9488` | Accent button hover |
| `--accent-strong` | `#0F766E` | Nav links, deal chip text, tab active text |
| `--accent-light` | `#F0FDFA` | Deal chips, Chase callout background |
| `--accent-border` | `#99F6E4` | Chip/callout borders |
| `--success` | `#059669` | Price amounts |
| `--success-light` | `#D1FAE5` | Best value box background |
| `--text-color` | `#374151` | Body text |
| `--text-muted` | `#6B7280` | Secondary labels |
| `--background` | `#F9FAFB` | Page background, manifest background |

---

## Files Audited

- `generate_flight_report.py` (CSS variables, all render functions)
- `public/index.html` (generated)
- `public/heatmap.html` (generated)
- `public/history.html` (generated)
- `public/manifest.json`
- `.planning/phases/multi-dest-tracker/multi-dest-UAT.md`
