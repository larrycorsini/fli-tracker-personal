"""Generate static HTML reports from best_direct.json for Netlify deployment."""

from __future__ import annotations

import html
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

from tracker_config import (
    FLIGHTS_JSON,
    INTERNATIONAL_REGIONS,
    MAX_FARE_GROUPS_PER_REGION,
    MAX_TIMES_PER_GROUP,
    OUTPUT_JSON,
    PREMIUM_DEAL_ORIGINS,
    PREMIUM_DEAL_OUTPUT_JSON,
    PREMIUM_DEALS_JSON,
    REGIONS,
    SITE_URL,
)
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
        "            position: relative; overflow: hidden;",
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
        "            .hero-airplane { animation: none !important; opacity: 0 !important; }",
        "        }",
        "        .hero-airplane {",
        "            position: absolute; top: 18%; right: -80px; width: 72px; height: 72px;",
        "            opacity: 0.35; pointer-events: none; z-index: 1;",
        "            animation: hero-fly 28s linear infinite;",
        "        }",
        "        @keyframes hero-fly {",
        "            0% { transform: translateX(110vw) translateY(0) rotate(-8deg); }",
        "            100% { transform: translateX(-120px) translateY(-24px) rotate(-8deg); }",
        "        }",
        "        @media (max-width: 640px) { .hero-airplane { width: 48px; height: 48px; top: 12%; } }",
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


def _existing_flights_json_has_data() -> bool:
    if not os.path.exists(FLIGHTS_JSON):
        return False
    try:
        with open(FLIGHTS_JSON, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return False
    region_data = payload.get("regionData", {})
    if not isinstance(region_data, dict):
        return False
    return any(
        isinstance(region_payload, dict) and region_payload.get("groupCount", 0) > 0
        for region_payload in region_data.values()
    )


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


def cap_region_flights(flights: list[dict]) -> list[dict]:
    """Cap fare groups and time options per group for display and JSON export."""
    priced = priced_flights(flights)
    if not priced:
        return []

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for flight in priced:
        key = (
            flight["origin"],
            flight.get("destination", ""),
            flight["airline"],
            flight["price"],
            flight["out_date"],
            flight["ret_date"],
        )
        groups[key].append(flight)

    sorted_groups = sorted(groups.items(), key=lambda item: item[0][3])[:MAX_FARE_GROUPS_PER_REGION]
    capped: list[dict] = []
    for _key, group_flights in sorted_groups:
        capped.extend(group_flights[:MAX_TIMES_PER_GROUP])
    return capped


def build_region_groups(
    flights: list[dict], region_name: str, hist_avg: dict[str, float | None]
) -> dict:
    """Serialize capped fare groups for client-side rendering."""
    capped = cap_region_flights(flights)
    priced = priced_flights(capped)
    if not priced:
        return {"groups": [], "best": None, "groupCount": 0}

    groups_map: dict[tuple, list[dict]] = defaultdict(list)
    for flight in priced:
        key = (
            flight["origin"],
            flight.get("destination", region_name),
            flight["airline"],
            flight["price"],
            flight["out_date"],
            flight["ret_date"],
        )
        groups_map[key].append(flight)

    groups_out: list[dict] = []
    for key, group_flights in sorted(groups_map.items(), key=lambda item: item[0][3]):
        origin, dest, airline, price, out_date, ret_date = key
        avg = hist_avg.get(region_name)
        drop_pct = 0
        if avg and price < avg:
            drop_pct = int(round((avg - price) / avg * 100))

        groups_out.append(
            {
                "origin": origin,
                "destination": dest,
                "airline": airline,
                "price": int(price),
                "points": int((int(price) * 100) / 1.25),
                "earn": int(price) * 5,
                "outDate": out_date,
                "retDate": ret_date,
                "outDateFmt": format_date(out_date),
                "retDateFmt": format_date(ret_date),
                "dropPct": drop_pct,
                "times": [
                    {
                        "outDepFmt": format_datetime(f["out_dep"]),
                        "retArrFmt": format_datetime(f["ret_arr"]),
                        "url": f.get("url") or "",
                    }
                    for f in group_flights
                ],
            }
        )

    best = min(priced, key=lambda row: row["price"])
    return {
        "groups": groups_out,
        "groupCount": len(groups_out),
        "best": {
            "airline": best["airline"],
            "destination": best.get("destination", region_name),
            "price": int(best["price"]),
            "outDateFmt": format_date(best["out_date"]),
            "retDateFmt": format_date(best["ret_date"]),
        },
    }


def build_flights_payload(
    all_results: dict[str, list[dict]],
    last_updated: str,
    hist_avg: dict[str, float | None],
) -> dict:
    """Build external JSON payload for lazy-loaded index page."""
    all_results = normalized_results(all_results)
    global_airlines: set[str] = set()
    regions_payload: dict[str, dict] = {}

    for region_name, flights in all_results.items():
        for flight in flights:
            if flight.get("airline"):
                global_airlines.add(flight["airline"])
        regions_payload[region_name] = build_region_groups(flights, region_name, hist_avg)

    deals = []
    for region_name, best in build_deal_board(all_results):
        if best:
            deals.append({"region": region_name, "price": int(best["price"])})
        else:
            deals.append({"region": region_name, "price": None})

    max_price = compute_max_price(all_results)
    return {
        "lastUpdated": last_updated,
        "siteUrl": SITE_URL,
        "intlTabs": INTERNATIONAL_REGIONS,
        "regions": list(REGIONS.keys()),
        "maxPriceDefault": max_price,
        "airlines": sorted(global_airlines),
        "deals": deals,
        "regionData": regions_payload,
    }


def write_flights_json(payload: dict) -> None:
    os.makedirs(os.path.dirname(FLIGHTS_JSON), exist_ok=True)
    atomic_write_json(FLIGHTS_JSON, payload)
    print(f"Flights JSON written: {FLIGHTS_JSON}")


def load_premium_deals() -> dict:
    """Load premium_deals.json produced by find_deals.py."""
    if not os.path.exists(PREMIUM_DEAL_OUTPUT_JSON):
        return {"deals": [], "origins": PREMIUM_DEAL_ORIGINS}
    try:
        with open(PREMIUM_DEAL_OUTPUT_JSON, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"deals": [], "origins": PREMIUM_DEAL_ORIGINS}
    if not isinstance(data, dict):
        return {"deals": [], "origins": PREMIUM_DEAL_ORIGINS}
    deals = data.get("deals", [])
    if not isinstance(deals, list):
        deals = []
    valid = [row for row in deals if isinstance(row, dict) and row.get("price") is not None]
    valid.sort(key=lambda row: float(row["price"]))
    origins = data.get("origins", PREMIUM_DEAL_ORIGINS)
    return {"deals": valid, "origins": origins, "last_run": data.get("last_run")}


def build_premium_deals_payload(raw: dict, last_updated: str) -> dict:
    """Serialize premium deals for the public dashboard JSON."""
    deals_out: list[dict] = []
    for deal in raw.get("deals", []):
        out_date = deal.get("out_date", "")
        ret_date = deal.get("ret_date", "")
        deals_out.append(
            {
                "destination": deal.get("destination", deal.get("airport", "")),
                "airport": deal.get("airport", ""),
                "regionLabel": deal.get("region_label", ""),
                "origin": deal.get("origin", "SLC"),
                "cabin": deal.get("cabin", ""),
                "price": int(deal["price"]),
                "outDate": out_date,
                "retDate": ret_date,
                "outDateFmt": format_date(out_date),
                "retDateFmt": format_date(ret_date),
                "airline": deal.get("airline", ""),
                "duration": deal.get("duration"),
                "stops": deal.get("stops"),
                "booking_url": deal.get("booking_url") or deal.get("url") or "",
            }
        )
    return {
        "lastUpdated": last_updated,
        "origins": raw.get("origins", PREMIUM_DEAL_ORIGINS),
        "deals": deals_out,
    }


def write_premium_deals_json(payload: dict) -> None:
    os.makedirs(os.path.dirname(PREMIUM_DEALS_JSON), exist_ok=True)
    atomic_write_json(PREMIUM_DEALS_JSON, payload)
    print(f"Premium deals JSON written: {PREMIUM_DEALS_JSON}")


def render_premium_deals_report(last_updated: str) -> None:
    """Write public/data/premium-deals.json from find_deals.py output."""
    raw = load_premium_deals()
    if os.path.exists(PREMIUM_DEAL_OUTPUT_JSON):
        mtime = datetime.fromtimestamp(os.path.getmtime(PREMIUM_DEAL_OUTPUT_JSON))
        premium_updated = mtime.strftime("%a, %b %d, %Y at %I:%M %p")
    else:
        premium_updated = last_updated
    payload = build_premium_deals_payload(raw, premium_updated)
    write_premium_deals_json(payload)


def render_index(all_results: dict[str, list[dict]], last_updated: str, hist_avg: dict[str, float | None]) -> None:
    all_results = normalized_results(all_results)
    payload = build_flights_payload(all_results, last_updated, hist_avg)
    write_flights_json(payload)

    regions_json = json.dumps(payload["regions"])
    max_price_init = payload["maxPriceDefault"]

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
            "        <div class='hero-airplane' aria-hidden='true'>",
            "            <svg viewBox='0 0 64 32' fill='none' xmlns='http://www.w3.org/2000/svg'>",
            "                <path d='M2 16 L14 14 L18 8 L26 8 L30 14 L62 16 L30 18 L26 24 L18 24 L14 18 Z' fill='#1A73E8'/>",
            "                <path d='M18 15 L46 16 L18 17 Z' fill='#1F2A37' opacity='0.35'/>",
            "            </svg>",
            "        </div>",
            "        <div class='max-w-2xl mx-auto relative z-10'>",
            "            <p class='text-sm font-bold tracking-[3px] text-gray-500 uppercase mb-4'>Weekend Escapes &amp; Global Travel</p>",
            "            <h1 class='page-header text-left'>Track your next adventure.</h1>",
            "            <p class='hero-text'>Daily curated fares from SLC and PVU across every tracked region. Points values optimized for Chase Sapphire Preferred.</p>",
            f"            <p class='text-sm text-gray-500 mb-6' x-data x-text=\"window.__FLI_META?.lastUpdated ? 'Last updated: ' + window.__FLI_META.lastUpdated : 'Last updated: {html.escape(last_updated)}'\"></p>",
            "            <a href='#premium-deals' class='dt-btn-primary focus-ring mr-3'>Premium deals</a>",
            "            <a href='#flights' class='dt-btn-primary focus-ring' style='background:transparent;color:var(--accent-interactive);border-color:var(--accent-interactive)'>Economy regions</a>",
            "        </div>",
            "    </section>",
            "    <section id='premium-deals' class='py-12 md:py-16 px-6 max-w-5xl mx-auto scroll-mt-24'",
            "             x-data='premiumDeals()' x-init='init()'>",
            "        <div class='mb-8 text-center'>",
            "            <h2 class='text-3xl font-bold text-gray-800 mb-2'>Premium deals from SLC</h2>",
            "            <p class='text-gray-500'>Business &amp; premium economy outlier fares · 7-night trips · day+14 to day+45</p>",
            "            <p class='text-sm text-gray-500 mt-2' x-show='lastUpdated' x-text=\"'Updated: ' + lastUpdated\"></p>",
            "        </div>",
            "        <div x-show='loading' class='text-center py-12 text-gray-500'>Loading premium deals…</div>",
            "        <div x-show='error' x-cloak class='text-center py-12 text-red-600' x-text='error'></div>",
            "        <div x-show='!loading && !error && deals.length === 0' x-cloak ",
            "             class='card-container bg-white border border-gray-200 p-8 text-center text-gray-500'>",
            "            No premium deals meet today's thresholds. Check back after the morning search (~6 AM).",
            "        </div>",
            "        <div x-show='!loading && !error && deals.length > 0' x-cloak ",
            "             class='card-container bg-white border border-gray-200 overflow-hidden divide-y divide-gray-100'>",
            "            <template x-for='(deal, i) in deals' :key=\"'premium-' + i\">",
            "                <article class='p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50 transition-colors'>",
            "                    <div class='flex-1 min-w-0'>",
            "                        <div class='flex flex-wrap items-center gap-2 mb-2'>",
            "                            <h3 class='text-xl font-bold text-gray-800' x-text='deal.destination'></h3>",
            "                            <span class='text-xs font-semibold px-3 py-1 rounded-full bg-gray-100 text-gray-600 border' x-text='deal.airport'></span>",
            "                            <span class='text-xs font-semibold px-3 py-1 rounded-full' style='background:var(--accent-interactive-muted);color:var(--accent-interactive);border:1px solid var(--accent-interactive-border)' x-text='deal.cabin'></span>",
            "                        </div>",
            "                        <p class='text-sm text-gray-500 mb-1'>",
            "                            <span x-text='deal.origin'></span> → <span x-text='deal.airport'></span>",
            "                            <span x-show='deal.regionLabel'> · </span>",
            "                            <span x-text='deal.regionLabel'></span>",
            "                        </p>",
            "                        <p class='text-[15px] text-gray-600'>",
            "                            <span class='font-semibold text-gray-800' x-text='deal.airline'></span>",
            "                            · <span x-text=\"deal.outDateFmt + ' — ' + deal.retDateFmt\"></span>",
            "                            <span x-show='deal.stops !== null && deal.stops !== undefined'> · ",
            "                                <span x-text=\"deal.stops === 0 ? 'Nonstop' : (deal.stops + ' stop' + (deal.stops !== 1 ? 's' : ''))\"></span>",
            "                            </span>",
            "                        </p>",
            "                    </div>",
            "                    <div class='flex items-center gap-4 shrink-0'>",
            "                        <div class='price-text'><span class='mr-1'>$</span><span x-text='deal.price'></span></div>",
            "                        <a :href='deal.booking_url || \"#\"' target='_blank' rel='noopener noreferrer' ",
            "                           class='btn-accent focus-ring text-sm' :aria-label=\"'Book ' + deal.destination + ' on Google Flights'\">Book</a>",
            "                    </div>",
            "                </article>",
            "            </template>",
            "        </div>",
            "    </section>",
            "    <script>",
            "        function premiumDeals() {",
            "            return {",
            "                loading: true,",
            "                error: null,",
            "                deals: [],",
            "                lastUpdated: null,",
            "                async init() {",
            "                    try {",
            "                        const resp = await fetch('data/premium-deals.json');",
            "                        if (!resp.ok) throw new Error('Could not load premium deals (' + resp.status + ')');",
            "                        const data = await resp.json();",
            "                        this.deals = data.deals || [];",
            "                        this.lastUpdated = data.lastUpdated || null;",
            "                        this.loading = false;",
            "                    } catch (err) {",
            "                        this.error = err.message || 'Failed to load premium deals';",
            "                        this.loading = false;",
            "                    }",
            "                },",
            "            };",
            "        }",
            "    </script>",
            "    <section id='flights' class='py-12 md:py-20 px-6 max-w-5xl mx-auto scroll-mt-24'",
            "             x-data='flightTracker()' x-init='init()' @scroll.window='showScrollTop = window.scrollY > 400'>",
            "        <div x-show='loading' class='text-center py-16 text-gray-500'>Loading flight data…</div>",
            "        <div x-show='error' x-cloak class='text-center py-16 text-red-600' x-text='error'></div>",
            "        <template x-if='!loading && !error'>",
            "        <div>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>Flight Options for <span x-text='activeTab'></span></h3>",
            "            <p class='text-gray-500' x-text=\"intlTabs.includes(activeTab) ? 'Departure: Any Day | Return: 7–10 Days later' : 'Departure: Wed / Thu / Fri | Return: Sat or Sun before 4 PM'\"></p>",
            "        </div>",
            "        <div class='mb-8 p-5 bg-white border border-gray-200 rounded-xl shadow-sm'>",
            "            <h4 class='text-xs font-bold uppercase tracking-wider text-gray-500 mb-3'>Best deals right now</h4>",
            "            <div class='flex flex-wrap gap-2'>",
            "                <template x-for='deal in deals' :key='deal.region'>",
            "                    <button type='button' x-show='deal.price !== null' @click='setTab(deal.region)'",
            "                        class='deal-chip focus-ring' x-text=\"deal.region + ' $' + deal.price\"></button>",
            "                    <span x-show='deal.price === null' class='deal-chip deal-chip-disabled' aria-disabled='true'",
            "                        :title=\"'No fares yet — check back after the morning update'\" x-text=\"deal.region + ' —'\"></span>",
            "                </template>",
            "            </div>",
            "        </div>",
            "        <div class='p-6 mb-8 callout-accent flex flex-col sm:flex-row justify-between gap-4'>",
            "            <div>",
            "                <h4 class='callout-accent-title mb-1'>Chase Sapphire Preferred</h4>",
            "                <p class='text-[15px] text-gray-700'><strong>Points:</strong> 1.25&cent; value shown. <strong>Cash:</strong> 5x via Chase Travel Portal.</p>",
            "            </div>",
            "            <a href='https://secure.chase.com/web/auth/dashboard#/dashboard/travel' target='_blank' rel='noopener noreferrer' class='shrink-0 text-center btn-accent focus-ring'>Go to Chase Travel</a>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll tab-fade border-b border-gray-200'>",
            "            <nav class='flex space-x-6 min-w-max px-1' role='tablist' aria-label='Destination regions'>",
            "                <template x-for='region in regions' :key='region'>",
            "                    <button type='button' role='tab' :aria-selected=\"activeTab === region\" @click='setTab(region)'",
            "                        :class=\"activeTab === region ? 'tab-active' : 'tab-inactive'\"",
            "                        class='tab-btn focus-ring whitespace-nowrap border-b-2 transition-colors' x-text='region'></button>",
            "                </template>",
            "            </nav>",
            "        </div>",
            "        <div class='flex justify-end mb-4'>",
            "            <button type='button' @click='showFilters = !showFilters' class='filter-toggle focus-ring text-sm font-semibold text-gray-500 hover:text-gray-800 flex items-center gap-1 bg-white border border-gray-200 px-4 py-2 rounded-full shadow-sm'>",
            "                <span x-text=\"showFilters ? 'Hide filters' : 'Show filters'\"></span>",
            "            </button>",
            "        </div>",
            "        <div x-show='showFilters' x-collapse x-cloak class='flex flex-col md:flex-row gap-6 mb-8 p-6 card-container bg-white border border-gray-200'>",
            "            <div class='flex-1'>",
            "                <label class='block text-sm font-semibold text-gray-700 mb-2'>Max Price: $<span x-text='maxPrice'></span></label>",
            f"                <input type='range' min='100' max='{max_price_init}' step='10' :value='maxPrice' @input='setMaxPrice($event.target.value)' class='w-full'>",
            "            </div>",
            "            <div class='flex-1'>",
            "                <label class='block text-sm font-semibold text-gray-700 mb-2'>Filter Airline</label>",
            "                <select :value='airlineFilter' @change='setAirlineFilter($event.target.value)' class='w-full border border-gray-300 rounded-md p-2 bg-white'>",
            "                    <option value='All'>All Airlines</option>",
            "                    <template x-for='airline in airlines' :key='airline'>",
            "                        <option :value='airline' x-text='airline'></option>",
            "                    </template>",
            "                </select>",
            "            </div>",
            "        </div>",
            "        <div class='card-container bg-white border border-gray-200 overflow-hidden'>",
            "            <div class='divide-y divide-gray-100'>",
            "                <template x-for='region in regions' :key=\"'panel-' + region\">",
            "                    <div x-show=\"activeTab === region\" x-cloak role='tabpanel'>",
            "                        <div x-show='!(regionData[region]?.groups?.length)' class='p-8 text-center text-gray-500'>",
            "                            No flights found for <span x-text='region'></span>. Check back after the next daily search (~6 AM).",
            "                        </div>",
            "                        <template x-for='(group, gi) in (regionData[region]?.groups || [])' :key=\"region + '-' + gi\">",
            "                            <div x-show=\"(airlineFilter === 'All' || airlineFilter === group.airline) && group.price <= maxPrice\" x-cloak>",
            "                                <div x-data='{ expanded: false }' class='hover:bg-gray-50 transition-colors'>",
            "                                    <button type='button' @click='expanded = !expanded' :aria-expanded='expanded'",
            "                                        class='focus-ring w-full text-left cursor-pointer p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between'>",
            "                                        <div class='flex-1 mb-4 md:mb-0'>",
            "                                            <div class='flex items-center flex-wrap gap-2 mb-2'>",
            "                                                <span class='text-[22px] font-bold text-gray-800' x-text='group.airline'></span>",
            "                                                <span class='text-xs font-semibold px-3 py-1 rounded-full bg-gray-100 text-gray-600 border'",
            "                                                    x-text=\"group.origin + ' → ' + group.destination\"></span>",
            "                                                <span x-show='group.dropPct > 0' class='deal-badge text-xs font-bold px-2 py-1 rounded-full'",
            "                                                    x-text=\"'↓' + group.dropPct + '% vs avg'\"></span>",
            "                                            </div>",
            "                                            <div class='text-[15px] text-gray-500'>",
            "                                                <span class='font-semibold text-gray-800'>Dates:</span>",
            "                                                <span x-text=\"group.outDateFmt + ' — ' + group.retDateFmt\"></span>",
            "                                                &nbsp;|&nbsp;",
            "                                                <span class='font-semibold accent-text' x-text=\"group.times.length + ' time option' + (group.times.length !== 1 ? 's' : '')\"></span>",
            "                                            </div>",
            "                                        </div>",
            "                                        <div class='flex items-center gap-6'>",
            "                                            <div class='text-right'>",
            "                                                <div class='price-text'><span class='mr-1'>$</span><span x-text='group.price'></span></div>",
            "                                                <div class='price-points' x-text=\"group.points.toLocaleString() + ' pts'\"></div>",
            "                                                <div class='text-xs earn-badge font-semibold' x-text=\"'+' + group.earn.toLocaleString() + ' pts'\"></div>",
            "                                            </div>",
            "                                            <div class='accent-text chevron-rotate' :class=\"expanded ? 'rotate-180' : ''\" style='transition: transform .3s' aria-hidden='true'>",
            "                                                <svg xmlns='http://www.w3.org/2000/svg' class='h-6 w-6' fill='none' viewBox='0 0 24 24' stroke='currentColor'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/></svg>",
            "                                            </div>",
            "                                        </div>",
            "                                    </button>",
            "                                    <div x-show='expanded' x-collapse x-cloak class='p-6 md:p-8 bg-gray-50 border-t border-gray-100'>",
            "                                        <h3 class='text-[13px] font-bold text-gray-500 uppercase tracking-wider mb-4'>Available Times</h3>",
            "                                        <div class='grid grid-cols-1 lg:grid-cols-2 gap-3'>",
            "                                            <template x-for='(time, ti) in group.times' :key=\"gi + '-' + ti\">",
            "                                                <div class='time-option-card'>",
            "                                                    <div class='time-option-times'>",
            "                                                        <div class='time-option-row'>",
            "                                                            <span class='time-option-label'>Outbound:</span>",
            "                                                            <span class='time-option-value' x-text='time.outDepFmt'></span>",
            "                                                        </div>",
            "                                                        <div class='time-option-row'>",
            "                                                            <span class='time-option-label'>Return:</span>",
            "                                                            <span class='time-option-value' x-text='time.retArrFmt'></span>",
            "                                                        </div>",
            "                                                    </div>",
            "                                                    <a :href='time.url || \"#\"' target='_blank' rel='noopener noreferrer' class='time-option-cta focus-ring'>Book</a>",
            "                                                </div>",
            "                                            </template>",
            "                                        </div>",
            "                                    </div>",
            "                                </div>",
            "                            </div>",
            "                        </template>",
            "                        <div class='p-8 text-center text-gray-500' x-show=\"regionData[region]?.groups?.length && !(regionData[region]?.groups || []).some(g => (airlineFilter === 'All' || airlineFilter === g.airline) && g.price <= maxPrice)\" x-cloak>",
            "                            No fares match your filters. Widen max price or choose All Airlines.",
            "                        </div>",
            "                        <div class='px-6 py-8' x-show='regionData[region]?.best'>",
            "                            <div class='flex items-start gap-4 p-6 best-value-box'>",
            "                                <div class='text-2xl' aria-hidden='true'>&#127775;</div>",
            "                                <div>",
            "                                    <div class='best-value-title mb-1' x-text=\"'Best value to ' + region\"></div>",
            "                                    <div class='text-gray-800 font-semibold text-lg'>",
            "                                        <span x-text=\"regionData[region].best.outDateFmt + ' — ' + regionData[region].best.retDateFmt\"></span>",
            "                                        &middot; <span x-text='regionData[region].best.airline'></span>",
            "                                        to <span x-text='regionData[region].best.destination'></span>",
            "                                        &middot; <span class='best-value-price' x-text=\"'$' + regionData[region].best.price\"></span>",
            "                                    </div>",
            "                                    <div class='text-sm text-gray-500 mt-1' x-text=\"regionData[region].groupCount + ' fare group' + (regionData[region].groupCount !== 1 ? 's' : '') + ' for this region'\"></div>",
            "                                </div>",
            "                            </div>",
            "                        </div>",
            "                        <p class='px-6 pb-6 text-center text-sm text-gray-500'>Use filters above to narrow results by price or airline.</p>",
            "                    </div>",
            "                </template>",
            "            </div>",
            "        </div>",
            "        </div>",
            "        </template>",
            "        <button type='button' x-show='showScrollTop' x-cloak @click='window.scrollTo({top: 0, behavior: \"smooth\"})' ",
            "            class='fixed bottom-6 right-6 scroll-top-btn focus-ring p-3 z-50' ",
            "            aria-label='Scroll to top'>",
            "            <svg xmlns='http://www.w3.org/2000/svg' class='h-6 w-6 mx-auto' fill='none' viewBox='0 0 24 24' stroke='currentColor'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2.5' d='M5 10l7-7m0 0l7 7m-7-7v18'/></svg>",
            "        </button>",
            "    </section>",
            f"    <script>window.__FLI_REGIONS = {regions_json};</script>",
            "    <script>",
            "        function flightTracker() {",
            "            return {",
            "                loading: true,",
            "                error: null,",
            "                activeTab: window.__FLI_REGIONS[0] || 'DFW',",
            "                regions: [],",
            "                deals: [],",
            "                regionData: {},",
            "                intlTabs: [],",
            "                airlines: [],",
            "                globalMaxPrice: 1500,",
            "                tabFilters: {},",
            "                showFilters: false,",
            "                showScrollTop: false,",
            "                get maxPrice() {",
            "                    const f = this.tabFilters[this.activeTab];",
            "                    return f ? f.maxPrice : this.globalMaxPrice;",
            "                },",
            "                get airlineFilter() {",
            "                    const f = this.tabFilters[this.activeTab];",
            "                    return f ? f.airlineFilter : 'All';",
            "                },",
            "                ensureTabFilters(tab) {",
            "                    if (!this.tabFilters[tab]) {",
            "                        this.tabFilters[tab] = { maxPrice: this.globalMaxPrice, airlineFilter: 'All' };",
            "                    }",
            "                },",
            "                setMaxPrice(val) {",
            "                    this.ensureTabFilters(this.activeTab);",
            "                    this.tabFilters[this.activeTab].maxPrice = Number(val);",
            "                },",
            "                setAirlineFilter(val) {",
            "                    this.ensureTabFilters(this.activeTab);",
            "                    this.tabFilters[this.activeTab].airlineFilter = val;",
            "                },",
            "                resolveInitialTab(regions) {",
            "                    const params = new URLSearchParams(window.location.search);",
            "                    const tabParam = params.get('tab');",
            "                    if (tabParam && regions.includes(tabParam)) return tabParam;",
            "                    const hash = decodeURIComponent(window.location.hash.slice(1));",
            "                    if (hash && regions.includes(hash)) return hash;",
            "                    return regions[0] || 'DFW';",
            "                },",
            "                updateUrl(tab) {",
            "                    const url = new URL(window.location.href);",
            "                    url.searchParams.set('tab', tab);",
            "                    url.hash = '';",
            "                    history.replaceState(null, '', url.pathname + url.search);",
            "                },",
            "                setTab(tab) {",
            "                    this.activeTab = tab;",
            "                    this.ensureTabFilters(tab);",
            "                    this.updateUrl(tab);",
            "                },",
            "                async init() {",
            "                    try {",
            "                        const resp = await fetch('data/flights.json');",
            "                        if (!resp.ok) throw new Error('Could not load flight data (' + resp.status + ')');",
            "                        const data = await resp.json();",
            "                        window.__FLI_META = { lastUpdated: data.lastUpdated };",
            "                        this.regions = data.regions || window.__FLI_REGIONS;",
            "                        this.deals = data.deals || [];",
            "                        this.regionData = data.regionData || {};",
            "                        this.intlTabs = data.intlTabs || [];",
            "                        this.airlines = data.airlines || [];",
            "                        this.globalMaxPrice = data.maxPriceDefault || 1500;",
            "                        this.activeTab = this.resolveInitialTab(this.regions);",
            "                        this.ensureTabFilters(this.activeTab);",
            "                        this.updateUrl(this.activeTab);",
            "                        this.loading = false;",
            "                    } catch (err) {",
            "                        this.error = err.message || 'Failed to load flights';",
            "                        this.loading = false;",
            "                    }",
            "                },",
            "            };",
            "        }",
            "    </script>",
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
    last_updated = datetime.now().strftime("%a, %b %d, %Y at %I:%M %p")
    if os.path.exists(OUTPUT_JSON):
        mtime = datetime.fromtimestamp(os.path.getmtime(OUTPUT_JSON))
        last_updated = mtime.strftime("%a, %b %d, %Y at %I:%M %p")

    if not all_results:
        print("No flight data found.")
        render_premium_deals_report(last_updated)
        return

    has_priced = any(priced_flights(flights) for flights in all_results.values())
    if not has_priced:
        render_premium_deals_report(last_updated)
        if _existing_flights_json_has_data():
            print("No flight data in best_direct.json — keeping existing reports.")
            return
        print("No flight data found.")
        return

    hist_avg = update_history(all_results)
    render_index(all_results, last_updated, hist_avg)
    render_premium_deals_report(last_updated)
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
