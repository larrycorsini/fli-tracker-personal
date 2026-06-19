"""Generate static HTML reports from best_direct.json for Netlify deployment."""

from __future__ import annotations

import html
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

from tracker_config import INTERNATIONAL_REGIONS, OUTPUT_JSON, REGIONS, SITE_URL
from tracker_io import atomic_write_json, atomic_write_text

ALPINE_CORE = "https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js"
ALPINE_COLLAPSE = "https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.14.9/dist/cdn.min.js"


def _parse_datetime(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str)
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def format_date(dt_str: str) -> str:
    dt = _parse_datetime(dt_str)
    if dt is None:
        return "—"
    return dt.strftime("%a, %b %d")


def format_datetime(dt_str: str) -> str:
    dt = _parse_datetime(dt_str)
    if dt is None:
        return "—"
    return dt.strftime("%a, %b %d, %I:%M %p")


def format_chart_date(dt_str: str) -> str:
    dt = _parse_datetime(dt_str)
    if dt is None:
        return "—"
    return dt.strftime("%a %b %d")


def priced_flights(flights: list[dict]) -> list[dict]:
    return [f for f in flights if f.get("price") is not None]


def compute_max_price(all_results: dict[str, list[dict]]) -> int:
    prices = [f["price"] for flights in all_results.values() for f in priced_flights(flights)]
    if not prices:
        return 1500
    return max(1500, int((max(prices) + 49) // 50 * 50))


def get_base_html_head(title: str, description: str, *, extra_scripts: list[str] | None = None) -> list[str]:
    scripts = extra_scripts or []
    head = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"    <title>{html.escape(title)}</title>",
        f"    <meta name='description' content='{html.escape(description)}'>",
        "    <link rel='manifest' href='manifest.json'>",
        "    <meta name='apple-mobile-web-app-capable' content='yes'>",
        "    <meta name='apple-mobile-web-app-status-bar-style' content='black-translucent'>",
        "    <link rel='apple-touch-icon' href='apple-touch-icon.png'>",
        "    <script src='https://cdn.tailwindcss.com'></script>",
        f"    <script defer src='{ALPINE_COLLAPSE}'></script>",
        f"    <script defer src='{ALPINE_CORE}'></script>",
        "    <link rel='preconnect' href='https://fonts.googleapis.com'>",
        "    <link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>",
        "    <link href='https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap' rel='stylesheet'>",
        "    <style>",
        "        :root {",
        "            --brand-primary: #1F2A37;",
        "            --brand-primary-hover: #374151;",
        "            --accent-interactive: #1A73E8;",
        "            --accent-interactive-hover: #1557B0;",
        "            --accent-interactive-muted: #E8F0FE;",
        "            --accent-interactive-border: #AECBFA;",
        "            --price-positive: #188038;",
        "            --earn-badge: #137333;",
        "            --deal-badge-bg: #D1FAE5;",
        "            --deal-badge-text: #065F46;",
        "            --best-value-bg: #ECFDF5;",
        "            --best-value-border: #A7F3D0;",
        "            --best-value-text: #047857;",
        "            --heatmap-low: #188038;",
        "            --heatmap-mid: #F9AB00;",
        "            --heatmap-high: #D93025;",
        "            --text-primary: #111827;",
        "            --text-secondary: #6B7280;",
        "            --text-muted: #9CA3AF;",
        "            --text-color: var(--text-primary);",
        "            --surface-page: #F9FAFB;",
        "            --surface-card: #FFFFFF;",
        "            --surface-muted: #F3F4F6;",
        "            --border-default: #E5E7EB;",
        "            --surface: var(--surface-card);",
        "            --background: var(--surface-page);",
        "            --success: #188038;",
        "            --warning: #F9AB00;",
        "            --warning-text: #111827;",
        "            --font-family-sans-serif: 'Roboto', system-ui, sans-serif;",
        "            --button--primary-background-color: var(--accent-interactive);",
        "            --button--primary-border: 2px solid var(--accent-interactive);",
        "            --button--primary-color: #ffffff;",
        "            --button--primary--hover-background-color: var(--accent-interactive-hover);",
        "            --button--primary--hover-border: 2px solid var(--accent-interactive-hover);",
        "            --button--primary--hover-box-shadow: 0px 4px 12px rgba(26, 115, 232, 0.25);",
        "        }",
        "        body { font-family: var(--font-family-sans-serif); -webkit-font-smoothing: antialiased; letter-spacing: -.01em; background: var(--background); color: var(--text-color); overflow-x: hidden; }",
        "        .skip-link { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; z-index: 100; }",
        "        .skip-link:focus { position: fixed; top: 12px; left: 12px; width: auto; height: auto; padding: 12px 20px; background: var(--accent-interactive); color: #fff; font-weight: 700; font-size: 14px; border-radius: 8px; box-shadow: 0 4px 12px rgba(26,115,232,0.35); text-decoration: none; }",
        "        .hero-section {",
        "            background-image: linear-gradient(to right, rgba(249,250,251,0.97) 20%, rgba(249,250,251,0.55) 100%),",
        "                url('https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1920&q=80');",
        "            background-size: cover; background-position: center;",
        "        }",
        "        h1, .page-header { font-weight: 700; font-size: 48px; line-height: 1.2; color: var(--brand-primary); margin-bottom: 20px; letter-spacing: -0.02em; }",
        "        @media (max-width: 640px) { h1, .page-header { font-size: 40px; } }",
        "        p.hero-text { font-size: 20px; line-height: 1.6; color: var(--text-color); opacity: 0.85; margin-bottom: 24px; }",
        "        .dt-btn-primary {",
        "            background: var(--button--primary-background-color); border: var(--button--primary-border);",
        "            color: var(--button--primary-color); border-radius: 40px; font-weight: 700;",
        "            padding: 12px 32px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center;",
        "            text-decoration: none; text-transform: uppercase; letter-spacing: 1px; font-size: 14px; transition: all .3s ease;",
        "        }",
        "        .dt-btn-primary:hover {",
        "            background: var(--button--primary--hover-background-color);",
        "            box-shadow: var(--button--primary--hover-box-shadow); transform: translateY(-2px); color: #fff;",
        "        }",
        "        .btn-accent {",
        "            background: var(--accent-interactive); color: #fff; font-weight: 700; border-radius: 8px;",
        "            padding: 12px 24px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center;",
        "            transition: background .2s ease;",
        "        }",
        "        .btn-accent:hover { background: var(--accent-interactive-hover); color: #fff; }",
        "        .price-text { font-weight: 500; font-size: 32px; color: var(--price-positive); display: flex; justify-content: flex-end; }",
        "        .price-points { font-weight: 500; font-size: 14px; color: var(--brand-primary); margin-top: 4px; text-align: right; }",
        "        .earn-badge { color: var(--earn-badge); }",
        "        .card-container { border-radius: 12px; box-shadow: 0 10px 40px -10px rgba(31, 42, 55, 0.08); }",
        "        .nav-logo { font-size: 24px; font-weight: 700; color: var(--brand-primary); letter-spacing: 2px; text-transform: uppercase; }",
        "        .nav-link-accent { color: var(--accent-interactive); font-weight: 700; }",
        "        .nav-link-accent:hover { color: var(--accent-interactive-hover); }",
        "        .tab-scroll { scroll-behavior: smooth; -webkit-overflow-scrolling: touch; }",
        "        .tab-fade { mask-image: linear-gradient(to right, transparent, black 12px, black calc(100% - 12px), transparent); }",
        "        .tab-active { border-bottom-color: var(--accent-interactive) !important; color: var(--accent-interactive) !important; font-weight: 700; }",
        "        .tab-inactive { border-color: transparent; color: var(--text-muted); font-weight: 500; }",
        "        .tab-inactive:hover { color: var(--text-color); }",
        "        .tab-btn { min-height: 44px; padding: 12px 16px; }",
        "        .deal-chip {",
        "            font-size: 14px; padding: 10px 16px; min-height: 44px; border-radius: 9999px;",
        "            border: 1px solid var(--accent-interactive-border); background: var(--accent-interactive-muted); color: var(--brand-primary);",
        "            transition: background .2s ease; cursor: pointer;",
        "        }",
        "        .deal-chip:hover { background: #DCE8FC; }",
        "        .deal-chip-disabled {",
        "            opacity: 0.6; cursor: not-allowed; border-color: #E5E7EB; background: #F3F4F6; color: var(--text-muted);",
        "        }",
        "        .deal-chip-disabled:hover { background: #F3F4F6; }",
        "        .deal-badge { background: var(--deal-badge-bg); color: var(--deal-badge-text); }",
        "        .best-value-box { background: var(--best-value-bg); border: 1px solid var(--best-value-border); border-radius: 16px; }",
        "        .best-value-title { color: var(--best-value-text); font-weight: 700; text-transform: uppercase; letter-spacing: .08em; font-size: 12px; }",
        "        .best-value-price { color: var(--best-value-text); font-weight: 700; }",
        "        .callout-accent {",
        "            background: var(--accent-interactive-muted); border: 1px solid var(--accent-interactive-border);",
        "            border-left: 4px solid var(--accent-interactive); border-radius: 16px;",
        "        }",
        "        .callout-accent-title { color: var(--accent-interactive); font-weight: 700; text-transform: uppercase; letter-spacing: .08em; font-size: 12px; }",
        "        .accent-text { color: var(--accent-interactive); }",
        "        .scroll-top-btn {",
        "            background: var(--accent-interactive); color: #fff; width: 50px; height: 50px; border-radius: 9999px;",
        "            box-shadow: 0 4px 14px rgba(31, 42, 55, 0.2); transition: background .2s ease;",
        "        }",
        "        .scroll-top-btn:hover { background: var(--accent-interactive-hover); }",
        "        .filter-toggle { min-height: 44px; }",
        "        .heatmap-cell { display: block; padding: 12px; border-radius: 8px; text-align: center; text-decoration: none; border: 1px solid transparent; transition: opacity .15s ease; }",
        "        .heatmap-cell:hover { opacity: 0.92; }",
        "        .heatmap-low { background: var(--heatmap-low); color: #fff; }",
        "        .heatmap-mid { background: var(--heatmap-mid); color: #111827; }",
        "        .heatmap-high { background: var(--heatmap-high); color: #fff; }",
        "        .focus-ring:focus-visible { outline: none; box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--accent-interactive); }",
        "        .time-option-card {",
        "            display: flex; flex-direction: column; gap: 10px; padding: 12px 16px;",
        "            background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 8px;",
        "        }",
        "        @media (min-width: 640px) {",
        "            .time-option-card { flex-direction: row; align-items: center; justify-content: space-between; gap: 16px; }",
        "        }",
        "        .time-option-times { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }",
        "        .time-option-row {",
        "            display: grid; grid-template-columns: 5.5rem 1fr; gap: 0 0.5rem; align-items: baseline;",
        "            font-size: 14px; line-height: 1.4; color: var(--text-primary);",
        "        }",
        "        .time-option-label { font-weight: 500; color: var(--text-secondary); white-space: nowrap; }",
        "        .time-option-value { white-space: nowrap; font-variant-numeric: tabular-nums; }",
        "        .time-option-cta {",
        "            flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center;",
        "            background: var(--accent-interactive); color: #fff; font-weight: 600; font-size: 13px;",
        "            padding: 6px 14px; border-radius: 6px; text-decoration: none; transition: background .2s ease;",
        "            width: 100%; min-height: 32px;",
        "        }",
        "        @media (min-width: 640px) { .time-option-cta { width: auto; } }",
        "        .time-option-cta:hover { background: var(--accent-interactive-hover); color: #fff; }",
        "        .nav-shell { transition: padding 200ms ease; }",
        "        .nav-links { transition: opacity 200ms ease, max-height 200ms ease; }",
        "        @media (max-width: 767px) {",
        "            .nav-links { max-height: 44px; opacity: 1; }",
        "            .nav-shell-compact .nav-links { opacity: 0; max-height: 0; overflow: hidden; pointer-events: none; }",
        "            .nav-shell-compact.nav-shell { padding-top: 8px; padding-bottom: 8px; gap: 0; }",
        "        }",
        "        @media (prefers-reduced-motion: reduce) {",
        "            .chevron-rotate { transition: none !important; }",
        "            html { scroll-behavior: auto; }",
        "            .nav-shell, .nav-links { transition: none !important; }",
        "        }",
        "        [x-cloak] { display: none !important; }",
        "    </style>",
    ]
    head.extend(scripts)
    head.extend(["</head>", "<body class='antialiased bg-gray-50 text-gray-800 overflow-x-hidden'>"])
    return head


def get_skip_link(target: str, label: str) -> str:
    return f"    <a href='{html.escape(target)}' class='skip-link focus-ring'>{html.escape(label)}</a>"


_NAV_LINK_CLASS = (
    "text-xs sm:text-sm font-bold uppercase tracking-wider focus-ring rounded "
    "px-1 py-2 min-h-[44px] inline-flex items-center"
)
_NAV_SHELL_CLASS = (
    "max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex flex-col sm:flex-row "
    "justify-between items-center gap-3 min-h-[60px] sm:min-h-[72px]"
)


def render_nav(active_page: str, links: list[tuple[str, str, bool]]) -> list[str]:
    """Render the shared site header nav.

    Args:
        active_page: Page id for aria-current (``index``, ``heatmap``, ``history``).
        links: ``(href, label_html, accent)`` tuples for right-side nav links.
    """
    page_href = {"index": "index.html", "heatmap": "heatmap.html", "history": "history.html"}
    current_href = page_href.get(active_page, "")

    link_lines: list[str] = []
    for href, label, accent in links:
        if accent:
            link_class = f"{_NAV_LINK_CLASS} nav-link-accent"
        else:
            link_class = f"{_NAV_LINK_CLASS} text-gray-500 hover:opacity-80"
        aria = " aria-current='page'" if href == current_href else ""
        link_lines.append(
            f"                <a href='{html.escape(href)}' class='{link_class}'{aria}>{label}</a>"
        )

    return [
        "    <nav class='bg-white shadow-sm border-b border-gray-100 sticky top-0 z-50'",
        "         x-data='{ navCompact: false }'",
        "         @scroll.window='navCompact = window.innerWidth < 768 && window.scrollY > 40'",
        "         @resize.window='if (window.innerWidth >= 768) navCompact = false'>",
        f"        <div class='{_NAV_SHELL_CLASS} nav-shell' :class=\"{{ 'nav-shell-compact': navCompact }}\">",
        "            <a href='index.html' class='nav-logo no-underline'>Fli-Tracker</a>",
        "            <div class='nav-links flex items-center gap-4 sm:gap-6' :inert='navCompact' :aria-hidden='navCompact'>",
        *link_lines,
        "            </div>",
        "        </div>",
        "    </nav>",
    ]


def get_footer(nav_links: list[tuple[str, str]] | None = None) -> list[str]:
    links_html = ""
    if nav_links:
        links_html = " &nbsp;&middot;&nbsp; ".join(
            f"<a href='{html.escape(href)}' class='text-gray-400 hover:text-white transition-colors'>{html.escape(label)}</a>"
            for label, href in nav_links
        )
    return [
        "    <footer class='text-white py-12 mt-12' style='background: var(--brand-primary);'>",
        "        <div class='max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6 text-center md:text-left'>",
        "            <div>",
        "                <div class='nav-logo text-white mb-2'>Fli-Tracker</div>",
        "                <p class='text-gray-400 text-sm'>Generated automatically. Updated every morning at 6 AM.</p>",
        "            </div>",
        f"            <div class='text-sm flex flex-wrap justify-center gap-4'>{links_html}</div>",
        "            <div class='text-sm text-gray-600'>&copy; 2026 Fli-Tracker</div>",
        "        </div>",
        "    </footer>",
        "    <script>",
        "        if ('serviceWorker' in navigator) {",
        "            window.addEventListener('load', () => {",
        "                navigator.serviceWorker.register('/sw.js').catch(err => console.error('SW registration failed:', err));",
        "            });",
        "        }",
        "    </script>",
        "</body>",
        "</html>",
    ]


def normalized_results(all_results: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Ensure every configured region key exists (empty list when no fares)."""
    return {name: all_results.get(name, []) for name in REGIONS}


def load_results() -> dict[str, list[dict]]:
    if not os.path.exists(OUTPUT_JSON):
        return {}
    with open(OUTPUT_JSON, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return normalized_results({"DFW": data})
    if isinstance(data, dict):
        return normalized_results(data)
    return normalized_results({})


def region_history_destinations(region_name: str) -> list[str]:
    """Destination keys in search_history for a region (name plus legacy airport codes)."""
    aliases = [region_name]
    for code in REGIONS.get(region_name, {}).get("destinations", []):
        if code not in aliases:
            aliases.append(code)
    return aliases


def fetch_region_daily_mins(
    cursor: sqlite3.Cursor, region_name: str, *, limit: int = 14
) -> list[tuple[str, float]]:
    """Lowest price per day for a region, merging region-name and legacy airport rows."""
    dests = region_history_destinations(region_name)
    placeholders = ",".join("?" * len(dests))
    cursor.execute(
        f"""
        SELECT SUBSTR(searched_at, 1, 10) AS day, MIN(price) AS min_price
        FROM search_history
        WHERE destination IN ({placeholders})
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
        """,
        (*dests, limit),
    )
    return cursor.fetchall()


def log_region_price(
    cursor: sqlite3.Cursor, region_name: str, price: float, searched_at: str
) -> None:
    """Insert or lower today's logged price for a region (idempotent per day)."""
    day = searched_at[:10]
    cursor.execute(
        """
        SELECT id, price FROM search_history
        WHERE destination = ? AND SUBSTR(searched_at, 1, 10) = ?
        ORDER BY price ASC LIMIT 1
        """,
        (region_name, day),
    )
    row = cursor.fetchone()
    if row:
        if price < row[1]:
            cursor.execute(
                "UPDATE search_history SET price = ?, searched_at = ? WHERE id = ?",
                (price, searched_at, row[0]),
            )
        return
    cursor.execute(
        "INSERT INTO search_history (origin, destination, departure_date, price, searched_at) VALUES (?, ?, ?, ?, ?)",
        ("SLC/PVU", region_name, "multi", price, searched_at),
    )


def update_history(all_results: dict[str, list[dict]]) -> dict[str, float | None]:
    """Log today's lowest price per region; return 14-day average per region."""
    all_results = normalized_results(all_results)
    averages: dict[str, float | None] = {region: None for region in REGIONS}
    db_path = "app/data/tracker.db"
    if not os.path.exists(db_path):
        return averages

    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for region_name in REGIONS:
        priced = priced_flights(all_results.get(region_name, []))
        if not priced:
            continue
        lowest = min(priced, key=lambda row: row["price"])["price"]
        log_region_price(cursor, region_name, lowest, today_str)

    conn.commit()

    for region_name in REGIONS:
        rows = fetch_region_daily_mins(cursor, region_name)
        if rows:
            averages[region_name] = sum(row[1] for row in rows) / len(rows)

    conn.close()
    return averages


def build_deal_board(all_results: dict[str, list[dict]]) -> list[tuple[str, dict | None]]:
    """Return all configured regions; None fare when no priced flights (disabled pill)."""
    deals: list[tuple[str, dict | None]] = []
    for region_name in REGIONS:
        flights = all_results.get(region_name, [])
        best_priced = priced_flights(flights)
        best = min(best_priced, key=lambda row: row["price"]) if best_priced else None
        deals.append((region_name, best))
    deals.sort(key=lambda item: (item[1] is None, item[1]["price"] if item[1] else 0))
    return deals


def render_index(all_results: dict[str, list[dict]], last_updated: str, hist_avg: dict[str, float | None]) -> None:
    all_results = normalized_results(all_results)
    regions = list(REGIONS.keys())
    intl_tabs = INTERNATIONAL_REGIONS
    intl_json = json.dumps(intl_tabs)
    max_price_init = compute_max_price(all_results)
    deals = build_deal_board(all_results)

    global_airlines: set[str] = set()
    for flights in all_results.values():
        for flight in flights:
            if flight.get("airline"):
                global_airlines.add(flight["airline"])

    first_tab = regions[0] if regions else "DFW"
    alpine_init = (
        f"{{ activeTab: {json.dumps(first_tab)}, maxPrice: {max_price_init}, "
        f"airlineFilter: {json.dumps('All')}, "
        f"showFilters: false, intlTabs: {intl_json}, showScrollTop: false }}"
    )

    lines = get_base_html_head(
        "Fli-Tracker | Multi-Destination Flight Search",
        "Daily curated flights from SLC/PVU to DFW, California, Cancun, Europe, Japan, and more.",
    )
    lines.append(get_skip_link("#flights", "Skip to flights"))
    lines.extend(
        render_nav(
            "index",
            [
                ("heatmap.html", "Heatmap", False),
                ("history.html", "Trends &rarr;", True),
            ],
        )
    )
    lines.extend(
        [
            "    <section class='hero-section py-16 md:py-28 px-6'>",
            "        <div class='max-w-2xl mx-auto'>",
            "            <p class='text-sm font-bold tracking-[3px] text-gray-500 uppercase mb-4'>Weekend Escapes &amp; Global Travel</p>",
            "            <h1 class='page-header text-left'>Track your next adventure.</h1>",
            "            <p class='hero-text'>Daily curated fares from SLC and PVU across every tracked region. Points values optimized for Chase Sapphire Preferred.</p>",
            f"            <p class='text-sm text-gray-500 mb-6'>Last updated: {html.escape(last_updated)}</p>",
            "            <a href='#flights' class='dt-btn-primary focus-ring'>View flight options</a>",
            "        </div>",
            "    </section>",
            f"    <section id='flights' class='py-12 md:py-20 px-6 max-w-5xl mx-auto scroll-mt-24' x-data='{alpine_init}' @scroll.window='showScrollTop = window.scrollY > 400'>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>Flight Options for <span x-text='activeTab'></span></h3>",
            "            <p class='text-gray-500' x-text=\"intlTabs.includes(activeTab) ? 'Departure: Any Day | Return: 7–10 Days later' : 'Departure: Wed / Thu / Fri | Return: Sat or Sun before 4 PM'\"></p>",
            "        </div>",
        ]
    )

    lines.append("        <div class='mb-8 p-5 bg-white border border-gray-200 rounded-xl shadow-sm'>")
    lines.append("            <h4 class='text-xs font-bold uppercase tracking-wider text-gray-500 mb-3'>Best deals right now</h4>")
    lines.append("            <div class='flex flex-wrap gap-2'>")
    for region_name, best in deals:
        region_esc = html.escape(region_name)
        if best:
            price = int(best["price"])
            lines.append(
                f"                <button type='button' @click=\"activeTab = '{region_esc}'\" "
                f"class='deal-chip focus-ring'>{region_esc} <strong>${price}</strong></button>"
            )
        else:
            lines.append(
                f"                <span class='deal-chip deal-chip-disabled' aria-disabled='true' "
                f"title='No fares yet — check back after the morning update'>{region_esc} —</span>"
            )
    lines.append("            </div>")
    lines.append("        </div>")

    lines.extend(
        [
            "        <div class='p-6 mb-8 callout-accent flex flex-col sm:flex-row justify-between gap-4'>",
            "            <div>",
            "                <h4 class='callout-accent-title mb-1'>Chase Sapphire Preferred</h4>",
            "                <p class='text-[15px] text-gray-700'><strong>Points:</strong> 1.25&cent; value shown. <strong>Cash:</strong> 5x via Chase Travel Portal.</p>",
            "            </div>",
            "            <a href='https://secure.chase.com/web/auth/dashboard#/dashboard/travel' target='_blank' rel='noopener noreferrer' class='shrink-0 text-center btn-accent focus-ring'>Go to Chase Travel</a>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll tab-fade border-b border-gray-200'>",
            "            <nav class='flex space-x-6 min-w-max px-1' role='tablist' aria-label='Destination regions'>",
        ]
    )

    for region in regions:
        region_esc = html.escape(region)
        lines.append(
            f"                <button type='button' role='tab' :aria-selected=\"activeTab === '{region_esc}'\" "
            f"@click=\"activeTab = '{region_esc}'\" "
            f":class=\"activeTab === '{region_esc}' ? 'tab-active' : 'tab-inactive'\" "
            f"class='tab-btn focus-ring whitespace-nowrap border-b-2 transition-colors'>{region_esc}</button>"
        )
    lines.append("            </nav>")
    lines.append("        </div>")

    lines.extend(
        [
            "        <div class='flex justify-end mb-4'>",
            "            <button type='button' @click='showFilters = !showFilters' class='filter-toggle focus-ring text-sm font-semibold text-gray-500 hover:text-gray-800 flex items-center gap-1 bg-white border border-gray-200 px-4 py-2 rounded-full shadow-sm'>",
            "                <span x-text=\"showFilters ? 'Hide filters' : 'Show filters'\"></span>",
            "            </button>",
            "        </div>",
            "        <div x-show='showFilters' x-collapse x-cloak class='flex flex-col md:flex-row gap-6 mb-8 p-6 card-container bg-white border border-gray-200'>",
            "            <div class='flex-1'>",
            "                <label class='block text-sm font-semibold text-gray-700 mb-2'>Max Price: $<span x-text='maxPrice'></span></label>",
            f"                <input type='range' min='100' max='{max_price_init}' step='10' x-model.number='maxPrice' class='w-full'>",
            "            </div>",
            "            <div class='flex-1'>",
            "                <label class='block text-sm font-semibold text-gray-700 mb-2'>Filter Airline</label>",
            "                <select x-model='airlineFilter' class='w-full border border-gray-300 rounded-md p-2 bg-white'>",
            "                    <option value='All'>All Airlines</option>",
        ]
    )
    for airline in sorted(global_airlines):
        lines.append(f"                    <option value={json.dumps(airline)}>{html.escape(airline)}</option>")
    lines.append("                </select>")
    lines.append("            </div>")
    lines.append("        </div>")

    lines.append("        <div class='card-container bg-white border border-gray-200 overflow-hidden'>")
    lines.append("            <div class='divide-y divide-gray-100'>")

    fare_panel_counter = 0

    for region_name, flights_list in all_results.items():
        region_esc = html.escape(region_name)
        lines.append(f"                <div x-show=\"activeTab === '{region_esc}'\" x-cloak role='tabpanel'>")

        priced = priced_flights(flights_list)
        if not priced:
            lines.append(
                f"                    <div class='p-8 text-center text-gray-500'>"
                f"No flights found for {region_esc}. Check back after the next daily search (~6 AM).</div>"
            )
            lines.append("                </div>")
            continue

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for flight in priced:
            key = (
                flight["origin"],
                flight.get("destination", "DFW"),
                flight["airline"],
                flight["price"],
                flight["out_date"],
                flight["ret_date"],
            )
            groups[key].append(flight)

        sorted_groups = sorted(groups.items(), key=lambda item: item[0][3])
        visible_count = len(sorted_groups)
        filter_pairs = {(key[2], int(key[3])) for key, _ in sorted_groups}
        filter_meta = [{"airline": airline, "price": price} for airline, price in sorted(filter_pairs, key=lambda p: p[1])]
        filter_meta_json = json.dumps(filter_meta)

        for key, group_flights in sorted_groups:
            origin, dest, airline, price, out_date, ret_date = key
            airline_json = json.dumps(airline)
            price_int = int(price)
            pts = int((price_int * 100) / 1.25)
            earn = price_int * 5
            fare_panel_counter += 1
            panel_id = f"fare-panel-{fare_panel_counter}"

            lines.append(
                f"                    <div x-show='(airlineFilter === \"All\" || airlineFilter === {airline_json}) && {price_int} <= maxPrice' x-cloak>"
            )
            lines.append("                    <div x-data='{ expanded: false }' class='hover:bg-gray-50 transition-colors'>")
            lines.append(
                f"                        <button type='button' @click='expanded = !expanded' "
                f":aria-expanded='expanded' aria-controls='{panel_id}' "
                f"@keydown.enter.prevent='expanded = !expanded' @keydown.space.prevent='expanded = !expanded' "
                f"class='focus-ring w-full text-left cursor-pointer p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between'>"
            )
            lines.append("                            <div class='flex-1 mb-4 md:mb-0'>")
            lines.append("                                <div class='flex items-center flex-wrap gap-2 mb-2'>")
            lines.append(f"                                    <span class='text-[22px] font-bold text-gray-800'>{html.escape(airline)}</span>")
            lines.append(
                f"                                    <span class='text-xs font-semibold px-3 py-1 rounded-full bg-gray-100 text-gray-600 border'>{html.escape(origin)} &rarr; {html.escape(dest)}</span>"
            )
            avg = hist_avg.get(region_name)
            if avg and price < avg:
                drop_pct = int(round((avg - price) / avg * 100))
                if drop_pct > 0:
                    lines.append(
                        f"                                    <span class='deal-badge text-xs font-bold px-2 py-1 rounded-full'>&darr;{drop_pct}% vs avg</span>"
                    )
            lines.append("                                </div>")
            lines.append(
                f"                                <div class='text-[15px] text-gray-500'><span class='font-semibold text-gray-800'>Dates:</span> "
                f"{format_date(out_date)} &mdash; {format_date(ret_date)} &nbsp;|&nbsp; "
                f"<span class='font-semibold accent-text'>{len(group_flights)} time option{'s' if len(group_flights) != 1 else ''}</span></div>"
            )
            lines.append("                            </div>")
            lines.append("                            <div class='flex items-center gap-6'>")
            lines.append("                                <div class='text-right'>")
            lines.append(f"                                    <div class='price-text'><span class='mr-1'>$</span>{price_int}</div>")
            lines.append(f"                                    <div class='price-points'>{pts:,} pts</div>")
            lines.append(f"                                    <div class='text-xs earn-badge font-semibold'>+{earn:,} pts</div>")
            lines.append("                                </div>")
            lines.append(
                "                                <div class='accent-text chevron-rotate' :class=\"expanded ? 'rotate-180' : ''\" style='transition: transform .3s' aria-hidden='true'>"
            )
            lines.append(
                "                                    <svg xmlns='http://www.w3.org/2000/svg' class='h-6 w-6' fill='none' viewBox='0 0 24 24' stroke='currentColor'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/></svg>"
            )
            lines.append("                                </div>")
            lines.append("                            </div>")
            lines.append("                        </button>")
            lines.append(
                f"                        <div id='{panel_id}' x-show='expanded' x-collapse x-cloak class='p-6 md:p-8 bg-gray-50 border-t border-gray-100'>"
            )
            lines.append("                            <h3 class='text-[13px] font-bold text-gray-500 uppercase tracking-wider mb-4'>Available Times</h3>")
            lines.append("                            <div class='grid grid-cols-1 lg:grid-cols-2 gap-3'>")

            for flight in group_flights:
                url = html.escape(flight.get("url") or "#", quote=True)
                out_time = html.escape(format_datetime(flight["out_dep"]))
                ret_time = html.escape(format_datetime(flight["ret_arr"]))
                book_label = f"Book outbound {out_time}, return {ret_time}"
                lines.append("                                <div class='time-option-card'>")
                lines.append("                                    <div class='time-option-times'>")
                lines.append("                                        <div class='time-option-row'>")
                lines.append("                                            <span class='time-option-label'>Outbound:</span>")
                lines.append(f"                                            <span class='time-option-value'>{out_time}</span>")
                lines.append("                                        </div>")
                lines.append("                                        <div class='time-option-row'>")
                lines.append("                                            <span class='time-option-label'>Return:</span>")
                lines.append(f"                                            <span class='time-option-value'>{ret_time}</span>")
                lines.append("                                        </div>")
                lines.append("                                    </div>")
                lines.append(
                    f"                                    <a href='{url}' target='_blank' rel='noopener noreferrer' "
                    f"class='time-option-cta focus-ring' aria-label='{html.escape(book_label)}'>Book</a>"
                )
                lines.append("                                </div>")

            lines.append("                            </div>")
            lines.append("                        </div>")
            lines.append("                    </div>")
            lines.append("                    </div>")

        lines.append(
            f"                    <div class='p-8 text-center text-gray-500' "
            f"x-show='activeTab === \"{region_esc}\" && "
            f"!{filter_meta_json}.some(f => (airlineFilter === \"All\" || airlineFilter === f.airline) && f.price <= maxPrice)' "
            f"x-cloak>No fares match your filters. Widen max price or choose All Airlines.</div>"
        )

        region_best = min(priced, key=lambda row: row["price"])
        lines.append("                    <div class='px-6 py-8'>")
        lines.append("                        <div class='flex items-start gap-4 p-6 best-value-box'>")
        lines.append("                            <div class='text-2xl' aria-hidden='true'>&#127775;</div>")
        lines.append("                            <div>")
        lines.append(f"                                <div class='best-value-title mb-1'>Best value to {region_esc}</div>")
        lines.append(
            f"                                <div class='text-gray-800 font-semibold text-lg'>{format_date(region_best['out_date'])} &mdash; "
            f"{format_date(region_best['ret_date'])} &middot; {html.escape(region_best['airline'])} to {html.escape(region_best.get('destination', region_name))} "
            f"&middot; <span class='best-value-price'>${int(region_best['price'])}</span></div>"
        )
        lines.append(f"                                <div class='text-sm text-gray-500 mt-1'>{visible_count} fare group{'s' if visible_count != 1 else ''} for this region</div>")
        lines.append("                            </div>")
        lines.append("                        </div>")
        lines.append("                    </div>")

        lines.append(
            "                    <p class='px-6 pb-6 text-center text-sm text-gray-500'>"
            "Use filters above to narrow results by price or airline.</p>"
        )
        lines.append("                </div>")

    lines.extend(
        [
            "            </div>",
            "        </div>",
            "        <button type='button' x-show='showScrollTop' x-cloak @click='window.scrollTo({top: 0, behavior: \"smooth\"})' ",
            "            class='fixed bottom-6 right-6 scroll-top-btn focus-ring p-3 z-50' ",
            "            aria-label='Scroll to top'>",
            "            <svg xmlns='http://www.w3.org/2000/svg' class='h-6 w-6 mx-auto' fill='none' viewBox='0 0 24 24' stroke='currentColor'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2.5' d='M5 10l7-7m0 0l7 7m-7-7v18'/></svg>",
            "        </button>",
            "    </section>",
        ]
    )
    lines.extend(
        get_footer(
            [
                ("Chase Travel", "https://secure.chase.com/web/auth/dashboard#/dashboard/travel"),
                ("Source Code", "https://github.com/punitarani/fli"),
            ]
        )
    )

    atomic_write_text("public/index.html", "\n".join(lines))
    print("Report generated: public/index.html")


def render_heatmap(all_results: dict[str, list[dict]]) -> None:
    all_results = normalized_results(all_results)
    heatmap_data: dict[str, dict[str, dict]] = {}
    for region_name, flights in all_results.items():
        by_date: dict[str, dict] = {}
        for flight in priced_flights(flights):
            day = flight["out_date"]
            if day not in by_date or flight["price"] < by_date[day]["price"]:
                by_date[day] = flight
        heatmap_data[region_name] = by_date

    regions = list(REGIONS.keys())
    first_region = regions[0]
    data_json = json.dumps(heatmap_data)
    heatmap_alpine = (
        f"{{ activeRegion: {json.dumps(first_region)}, "
        f"get heatmapData() {{ return window.HEATMAP_DATA }} }}"
    )

    lines = get_base_html_head(
        "Fli-Tracker | Calendar Heatmap",
        "Visual calendar heatmap of best flight prices from SLC/PVU by destination region.",
    )
    lines.extend(
        [
            f"    <script>window.HEATMAP_DATA = {data_json};</script>",
            get_skip_link("#main-content", "Skip to heatmap"),
            *render_nav("heatmap", [("index.html", "&larr; Back to Flights", True)]),
            f"    <section id='main-content' class='py-12 px-6 max-w-5xl mx-auto scroll-mt-24' x-data='{heatmap_alpine}'>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>Calendar Heatmap</h3>",
            "            <p class='text-gray-500'>Best outbound price per day — <span x-text='activeRegion'></span></p>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll tab-fade'>",
            "            <nav class='flex gap-4 min-w-max border-b border-gray-200 pb-1' role='tablist' aria-label='Destination regions'>",
        ]
    )
    for region in regions:
        region_esc = html.escape(region)
        lines.append(
            f"                <button type='button' role='tab' :aria-selected=\"activeRegion === '{region_esc}'\" "
            f"@click=\"activeRegion = '{region_esc}'\" "
            f":class=\"activeRegion === '{region_esc}' ? 'tab-active border-b-2' : 'tab-inactive'\" "
            f"class='tab-btn focus-ring whitespace-nowrap'>{region_esc}</button>"
        )
    lines.extend(
        [
            "            </nav>",
            "        </div>",
            "        <template x-for='region in Object.keys(heatmapData)' :key='region'>",
            "            <div x-show='activeRegion === region' x-cloak role='tabpanel' class='card-container bg-white border border-gray-200 p-6 overflow-x-auto'>",
            "                <p class='text-gray-500 text-center py-12' x-show='Object.keys(heatmapData[region] || {}).length === 0'>No data for this region yet.</p>",
            "                <div class='grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3' x-show='Object.keys(heatmapData[region] || {}).length > 0'>",
            "                    <template x-for='[date, flight] in Object.entries(heatmapData[region] || {}).sort((a,b) => a[0].localeCompare(b[0]))' :key='date'>",
            "                        <a x-show='flight.url' :href='flight.url' target='_blank' rel='noopener noreferrer' class='heatmap-cell focus-ring' :class=\"flight.price < 320 ? 'heatmap-low' : flight.price <= 500 ? 'heatmap-mid' : 'heatmap-high'\">",
            "                            <div class='text-xs opacity-90' x-text='new Date(date + \"T12:00:00\").toLocaleDateString(undefined, {weekday:\"short\", month:\"short\", day:\"numeric\"})'></div>",
            "                            <div class='text-lg font-bold' x-text=\"'$' + flight.price\"></div>",
            "                        </a>",
            "                        <div x-show='!flight.url' class='heatmap-cell' :class=\"flight.price < 320 ? 'heatmap-low' : flight.price <= 500 ? 'heatmap-mid' : 'heatmap-high'\">",
            "                            <div class='text-xs opacity-90' x-text='new Date(date + \"T12:00:00\").toLocaleDateString(undefined, {weekday:\"short\", month:\"short\", day:\"numeric\"})'></div>",
            "                            <div class='text-lg font-bold' x-text=\"'$' + flight.price\"></div>",
            "                        </div>",
            "                    </template>",
            "                </div>",
            "            </div>",
            "        </template>",
            "    </section>",
        ]
    )
    lines.extend(get_footer())
    atomic_write_text("public/heatmap.html", "\n".join(lines))
    print("Heatmap generated: public/heatmap.html")


def render_history(all_results: dict[str, list[dict]]) -> None:
    all_results = normalized_results(all_results)
    db_path = "app/data/tracker.db"
    history: dict[str, dict[str, list]] = {region: {"labels": [], "prices": []} for region in REGIONS}

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for region_name in REGIONS:
            rows = list(reversed(fetch_region_daily_mins(cursor, region_name)))
            history[region_name]["labels"] = [format_chart_date(row[0]) for row in rows]
            history[region_name]["prices"] = [row[1] for row in rows]
        conn.close()

    regions = list(REGIONS.keys())
    first = html.escape(regions[0])
    history_json = json.dumps(history)

    lines = get_base_html_head(
        "Fli-Tracker | Price History",
        "14-day price trends for flights from SLC/PVU by destination region.",
        extra_scripts=["    <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>"],
    )
    lines.extend(
        [
            get_skip_link("#main-content", "Skip to chart"),
            *render_nav(
                "history",
                [
                    ("heatmap.html", "Heatmap", False),
                    ("index.html", "&larr; Flights", True),
                ],
            ),
            f"    <section id='main-content' class='py-12 px-6 max-w-5xl mx-auto scroll-mt-24' x-data='historyPage()' x-init='init()'>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>14-Day Price Trends</h3>",
            "            <p class='text-gray-500'>Lowest fare for <span x-text='activeRegion'></span></p>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll tab-fade'>",
            "            <nav class='flex gap-4 min-w-max border-b border-gray-200 pb-1' role='tablist' aria-label='Destination regions'>",
        ]
    )
    for region in regions:
        region_esc = html.escape(region)
        lines.append(
            f"                <button type='button' role='tab' :aria-selected=\"activeRegion === '{region_esc}'\" "
            f"@click=\"activeRegion = '{region_esc}'\" "
            f":class=\"activeRegion === '{region_esc}' ? 'tab-active border-b-2' : 'tab-inactive'\" "
            f"class='tab-btn focus-ring whitespace-nowrap'>{region_esc}</button>"
        )
    lines.extend(
        [
            "            </nav>",
            "        </div>",
            "        <div role='tabpanel' class='card-container bg-white border border-gray-200 p-4 md:p-8' style='position:relative;height:50vh;min-height:300px'>",
            "            <canvas id='priceChart' x-show='hasData' x-cloak></canvas>",
            "            <p class='absolute inset-0 flex items-center justify-center text-gray-500' x-show='!hasData' x-cloak>No history yet for this region.</p>",
            "        </div>",
            "    </section>",
            f"    <script>window.HISTORY_DATA = {history_json}; window.HISTORY_DEFAULT = {json.dumps(regions[0])};</script>",
            "    <script>",
            "        function historyPage() {",
            "            return {",
            "                activeRegion: window.HISTORY_DEFAULT,",
            "                chart: null,",
            "                get hasData() {",
            "                    const d = window.HISTORY_DATA[this.activeRegion] || { labels: [], prices: [] };",
            "                    return d.labels && d.labels.length > 0;",
            "                },",
            "                init() { this.renderChart(); this.$watch('activeRegion', () => this.renderChart()); },",
            "                renderChart() {",
            "                    const canvas = document.getElementById('priceChart');",
            "                    if (!canvas) return;",
            "                    const d = window.HISTORY_DATA[this.activeRegion] || { labels: [], prices: [] };",
            "                    if (this.chart) this.chart.destroy();",
            "                    if (!d.labels.length) { this.chart = null; return; }",
            "                    const pointRadius = d.labels.length <= 2 ? 6 : 3;",
            "                    this.chart = new Chart(canvas.getContext('2d'), {",
            "                        type: 'line',",
            "                        data: {",
            "                            labels: d.labels,",
            "                            datasets: [{ data: d.prices, borderColor: '#1A73E8', backgroundColor: 'rgba(26,115,232,0.12)', fill: true, tension: 0.4, borderWidth: 3, pointRadius, pointHoverRadius: pointRadius + 2 }]",
            "                        },",
            "                        options: {",
            "                            responsive: true,",
            "                            maintainAspectRatio: false,",
            "                            plugins: { legend: { display: false } },",
            "                            scales: { y: { ticks: { callback: (v) => '$' + v } } }",
            "                        }",
            "                    });",
            "                }",
            "            };",
            "        }",
            "    </script>",
        ]
    )
    lines.extend(get_footer())
    atomic_write_text("public/history.html", "\n".join(lines))
    print("History generated: public/history.html")


def main() -> None:
    all_results = load_results()
    if not all_results:
        print("No flight data found.")
        return

    if os.path.exists(OUTPUT_JSON):
        mtime = datetime.fromtimestamp(os.path.getmtime(OUTPUT_JSON))
        last_updated = mtime.strftime("%a, %b %d, %Y at %I:%M %p")
    else:
        last_updated = datetime.now().strftime("%a, %b %d, %Y at %I:%M %p")

    hist_avg = update_history(all_results)
    render_index(all_results, last_updated, hist_avg)
    render_heatmap(all_results)
    render_history(all_results)

    manifest_path = "public/manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["description"] = (
            "Daily curated multi-destination flight tracking from SLC/PVU — DFW, California, Europe, and more."
        )
        manifest["theme_color"] = "#1F2A37"
        manifest["background_color"] = "#F9FAFB"
        atomic_write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
