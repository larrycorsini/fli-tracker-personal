---
phase: multi-dest-tracker
slug: multi-dest-tracker
status: approved
shadcn_initialized: false
preset: none
created: 2026-06-18
updated: 2026-06-18
site: https://flights.larrycorsini.com
generator: generate_flight_report.py
---

# Multi-Dest Tracker — UI Design Contract

> Visual and interaction contract for the static Alpine.js + Tailwind flight tracker (`public/index.html`, `heatmap.html`, `history.html`). **Implemented** in `generate_flight_report.py` (v1.1 UI overhaul).

**Brand direction (locked):** Primary `#1F2A37`, Google Flights–inspired UX, mobile-first, booking deep-links on every fare.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (static HTML generator) |
| Component library | Hand-built Tailwind CDN + Alpine.js 3.14 |
| Font | **Roboto** 400, 500, 700 |
| CSS delivery | `:root` tokens in `get_base_html_head()` |
| Breakpoints | Tailwind defaults (`sm` 640, `md` 768, `lg` 1024) |

---

## Design Tokens (Final Palette)

### Core brand & surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `--brand-primary` | `#1F2A37` | Logo, hero H1, footer, points line |
| `--brand-primary-hover` | `#374151` | Nav hover |
| `--surface-page` | `#F9FAFB` | Body (60%) |
| `--surface-card` | `#FFFFFF` | Cards, nav (30%) |
| `--surface-muted` | `#F3F4F6` | Expanded panels, hover rows |
| `--border-default` | `#E5E7EB` | Dividers |

### Text

| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#111827` | Headings, fare names |
| `--text-secondary` | `#6B7280` | Meta, labels |
| `--text-muted` | `#9CA3AF` | Footer secondary |

### Accent & actions

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent-interactive` | `#1A73E8` | CTAs, active tabs, chart, FAB |
| `--accent-interactive-hover` | `#1557B0` | Hover states |
| `--accent-interactive-muted` | `#E8F0FE` | Deal pills, Chase callout |
| `--accent-interactive-border` | `#AECBFA` | Pill borders |

### Semantic

| Token | Hex | Usage |
|-------|-----|-------|
| `--success` / `--price-positive` | `#188038` | Dollar prices |
| `--earn-badge` | `#137333` | +pts earn line |
| `--warning` | `#F9AB00` | Heatmap mid tier bg |
| `--warning-text` | `#111827` | Text on mid heatmap tier |
| `--heatmap-low` | `#188038` | Price &lt; $320 |
| `--heatmap-mid` | `#F9AB00` | $320–500 |
| `--heatmap-high` | `#D93025` | &gt; $500 |
| `--destructive` | `#D93025` | Reserved |

**60 / 30 / 10:** page gray + white cards dominate; accent blue/green on CTAs, tabs, prices, heatmap only.

---

## Typography

| Role | Size | Weight |
|------|------|--------|
| Display (hero) | 40px / 48px md | 700 |
| Section H3 | 28px (`text-3xl`) | 700 |
| Body | 15px | 400 |
| Price | 32px | 500 |
| Label uppercase | 12px | 700 |
| CTA | 14px uppercase | 700 |

---

## Spacing & touch

- Scale: 4 / 8 / 16 / 24 / 32 / 48 / 64 px
- Min tap targets: **44px** (tabs, chips, CTAs, nav links)
- FAB: 50×50px

---

## Mobile scroll behavior (nav)

**Breakpoint:** `< 768px` (below Tailwind `md`). Desktop (`md` and up) always shows full nav links.

| State | Trigger | Visible chrome |
|-------|---------|----------------|
| Expanded | `scrollY ≤ 40` on mobile | Logo **Fli-Tracker** + nav links (Heatmap, Trends, or page-specific links) |
| Compact | `scrollY > 40` on mobile | Logo **Fli-Tracker** only |

**Implementation (`render_nav()` in `generate_flight_report.py`):**

- Alpine `x-data="{ navCompact: false }"` on `<nav>`
- `@scroll.window` sets `navCompact` when `innerWidth < 768 && scrollY > 40`
- `@resize.window` resets `navCompact` when viewport ≥ 768px
- Links container: `.nav-links` — opacity + `max-height` collapse (not `display:none`) to avoid layout jank
- Shell: `.nav-shell` keeps `min-h-[60px]`; compact adds `.nav-shell-compact` → `py-2` (8px) + `gap: 0` on mobile only
- Transition: **200ms ease** on padding, opacity, max-height
- `prefers-reduced-motion`: disable nav transitions (instant state change)
- Compact links: `inert` + `aria-hidden="true"` so hidden links leave tab order
- Logo/title always visible and linked to `index.html`

**Touch targets:** When links are visible (expanded state), each link retains `min-h-[44px]`.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Hero CTA | **View flight options** |
| Time row CTA | **Select flight** |
| Chase CTA | **Go to Chase Travel** |
| Empty region | **No flights found for {region}.** Check back after the next daily search (~6 AM). |
| Filtered empty | **No fares match your filters.** Widen max price or choose All Airlines. |
| Heatmap empty | **No data for this region yet.** |
| History empty | **No history yet for this region.** |
| Skip links | Skip to flights / heatmap / chart |

---

## Accessibility

- WCAG AA contrast on text pairs (mid heatmap uses dark text on amber)
- `focus-visible` ring: 2px `#1A73E8` + offset
- Skip links on all pages
- `role="tablist"` / `role="tab"` / `aria-selected` / `role="tabpanel"` on all pages
- Fare expand: `<button>` with `aria-expanded`, `aria-controls`
- `prefers-reduced-motion` disables chevron animation and nav collapse transitions
- Booking links: `rel="noopener noreferrer"`

---

## Component notes

- **Deal board:** All 8 `REGIONS`; priced chips clickable; empty regions show **disabled pill** (`deal-chip-disabled`)
- **Hero:** Aviation photo + gradient overlay (unchanged)
- **Heatmap cells:** Link to `flight.url` when present; tier colors from tokens
- **manifest.json:** `theme_color` `#1F2A37`, `background_color` `#F9FAFB`

---

## Checker Sign-Off

| Dimension | Verdict | Notes |
|-----------|---------|-------|
| 1 Copywriting | **PASS** | Contract strings in generator |
| 2 Visuals | **PASS** | Hero, deal board, hierarchy |
| 3 Color | **PASS** | Purple retired; token-driven |
| 4 Typography | **PASS** | Roboto scale consolidated |
| 5 Spacing | **PASS** | 44px targets, tab scroll + fade |
| 6 Registry Safety | **PASS** | N/A (no shadcn) |

**Approval:** 2026-06-18

---

## Known follow-ups (non-blocking)

| ID | Item |
|----|------|
| INFO-01 | Heatmap $320/$500 thresholds global; intl may need per-region tiers |
| INFO-02 | Tailwind CDN runtime (CSP/cache) — acceptable for static deploy |
| INFO-03 | Filter-empty `x-show` embeds per-region JSON — consider `x-data` refactor if HTML size grows |

*Archive copy: `.planning/milestones/v1.1-phases/multi-dest-tracker/UI-SPEC.md`*
