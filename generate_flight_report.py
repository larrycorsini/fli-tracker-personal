"""Generate static HTML reports from best_direct.json for Netlify deployment."""

from __future__ import annotations

import html
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

from tracker_config import INTERNATIONAL_REGIONS, OUTPUT_JSON, REGIONS, SITE_URL

ALPINE_CORE = "https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js"
ALPINE_COLLAPSE = "https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.14.9/dist/cdn.min.js"


def format_date(dt_str: str) -> str:
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%a, %b %d")


def format_datetime(dt_str: str) -> str:
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%a, %b %d, %I:%M %p")


def format_chart_date(dt_str: str) -> str:
    dt = datetime.strptime(dt_str, "%Y-%m-%d")
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
        "    <link href='https://fonts.googleapis.com/css2?family=Raleway:wght@300;400;500;600;700;900&display=swap' rel='stylesheet'>",
        "    <style>",
        "        :root {",
        "            --primary: #1F2A37;",
        "            --primary-hover: #2D3A4A;",
        "            --accent: #14B8A6;",
        "            --accent-hover: #0D9488;",
        "            --accent-strong: #0F766E;",
        "            --accent-light: #F0FDFA;",
        "            --accent-border: #99F6E4;",
        "            --success: #059669;",
        "            --success-light: #D1FAE5;",
        "            --success-border: #6EE7B7;",
        "            --text-color: #374151;",
        "            --text-muted: #6B7280;",
        "            --surface: #FFFFFF;",
        "            --background: #F9FAFB;",
        "            --font-family-sans-serif: 'Raleway', sans-serif;",
        "            --button--primary-background-color: var(--primary);",
        "            --button--primary-border: 2px solid var(--primary);",
        "            --button--primary-color: #ffffff;",
        "            --button--primary--hover-background-color: var(--primary-hover);",
        "            --button--primary--hover-border: 2px solid var(--primary-hover);",
        "            --button--primary--hover-box-shadow: 0px 4px 12px rgba(31, 42, 55, 0.25);",
        "        }",
        "        body { font-family: var(--font-family-sans-serif); -webkit-font-smoothing: antialiased; letter-spacing: -.31px; background: var(--background); color: var(--text-color); }",
        "        .hero-section {",
        "            background-image: linear-gradient(to right, rgba(249,250,251,0.97) 20%, rgba(249,250,251,0.55) 100%),",
        "                url('https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1920&q=80');",
        "            background-size: cover; background-position: center;",
        "        }",
        "        h1, .page-header { font-weight: 900; font-size: 52px; line-height: 1.1; color: var(--primary); margin-bottom: 20px; }",
        "        @media (max-width: 640px) { h1, .page-header { font-size: 36px; } }",
        "        p.hero-text { font-size: 20px; line-height: 1.6; color: var(--text-color); margin-bottom: 24px; }",
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
        "            background: var(--accent); color: #fff; font-weight: 700; border-radius: 8px;",
        "            padding: 12px 24px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center;",
        "            transition: background .2s ease;",
        "        }",
        "        .btn-accent:hover { background: var(--accent-hover); color: #fff; }",
        "        .price-text { font-weight: 500; font-size: 32px; color: var(--success); display: flex; justify-content: flex-end; }",
        "        .price-points { font-weight: 600; font-size: 14px; color: var(--primary); margin-top: 4px; text-align: right; }",
        "        .card-container { border-radius: 12px; box-shadow: 0 10px 40px -10px rgba(31, 42, 55, 0.08); }",
        "        .nav-logo { font-size: 24px; font-weight: 900; color: var(--primary); letter-spacing: 2px; text-transform: uppercase; }",
        "        .nav-link-accent { color: var(--accent-strong); font-weight: 700; }",
        "        .nav-link-accent:hover { color: var(--accent-hover); }",
        "        .tab-scroll { scroll-behavior: smooth; -webkit-overflow-scrolling: touch; }",
        "        .tab-fade { mask-image: linear-gradient(to right, transparent, black 12px, black calc(100% - 12px), transparent); }",
        "        .tab-active { border-bottom-color: var(--accent) !important; color: var(--accent-strong) !important; font-weight: 700; }",
        "        .tab-inactive { border-color: transparent; color: var(--text-muted); font-weight: 500; }",
        "        .tab-inactive:hover { color: var(--text-color); }",
        "        .tab-btn { min-height: 44px; padding: 12px 16px; }",
        "        .deal-chip {",
        "            font-size: 14px; padding: 10px 16px; min-height: 44px; border-radius: 9999px;",
        "            border: 1px solid var(--accent-border); background: var(--accent-light); color: var(--accent-strong);",
        "            transition: background .2s ease;",
        "        }",
        "        .deal-chip:hover { background: #CCFBF1; }",
        "        .callout-accent {",
        "            background: var(--accent-light); border: 1px solid var(--accent-border);",
        "            border-left: 4px solid var(--accent); border-radius: 8px;",
        "        }",
        "        .callout-accent-title { color: var(--accent-strong); font-weight: 700; text-transform: uppercase; letter-spacing: .05em; font-size: 13px; }",
        "        .accent-text { color: var(--accent-strong); }",
        "        .scroll-top-btn {",
        "            background: var(--primary); color: #fff; width: 50px; height: 50px; border-radius: 9999px;",
        "            box-shadow: 0 4px 14px rgba(31, 42, 55, 0.25); transition: background .2s ease;",
        "        }",
        "        .scroll-top-btn:hover { background: var(--primary-hover); }",
        "        .filter-toggle { min-height: 44px; }",
        "        [x-cloak] { display: none !important; }",
        "    </style>",
    ]
    head.extend(scripts)
    head.extend(["</head>", "<body class='antialiased bg-gray-50 text-gray-800'>"])
    return head


def get_footer(nav_links: list[tuple[str, str]] | None = None) -> list[str]:
    links_html = ""
    if nav_links:
        links_html = " &nbsp;&middot;&nbsp; ".join(
            f"<a href='{html.escape(href)}' class='text-gray-400 hover:text-white transition-colors'>{html.escape(label)}</a>"
            for label, href in nav_links
        )
    return [
        "    <footer class='bg-gray-900 text-white py-12 mt-12'>",
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


def load_results() -> dict[str, list[dict]]:
    if not os.path.exists(OUTPUT_JSON):
        return {}
    with open(OUTPUT_JSON, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return {"DFW": data}
    return data


def update_history(all_results: dict[str, list[dict]]) -> dict[str, float | None]:
    """Log today's lowest price per region; return 14-day average per region."""
    averages: dict[str, float | None] = {region: None for region in all_results}
    db_path = "app/data/tracker.db"
    if not os.path.exists(db_path):
        return averages

    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for region_name, flights in all_results.items():
        priced = priced_flights(flights)
        if not priced:
            continue
        lowest = min(priced, key=lambda row: row["price"])["price"]
        cursor.execute(
            "INSERT INTO search_history (origin, destination, departure_date, price, searched_at) VALUES (?, ?, ?, ?, ?)",
            ("SLC/PVU", region_name, "multi", lowest, today_str),
        )

    conn.commit()

    for region_name in all_results:
        cursor.execute(
            """
            SELECT SUBSTR(searched_at, 1, 10) AS day, MIN(price) AS min_price
            FROM search_history
            WHERE destination = ?
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """,
            (region_name,),
        )
        rows = cursor.fetchall()
        if rows:
            averages[region_name] = sum(row[1] for row in rows) / len(rows)

    conn.close()
    return averages


def build_deal_board(all_results: dict[str, list[dict]]) -> list[tuple[str, dict]]:
    deals: list[tuple[str, dict]] = []
    for region_name, flights in all_results.items():
        priced = priced_flights(flights)
        if priced:
            deals.append((region_name, min(priced, key=lambda row: row["price"])))
    deals.sort(key=lambda item: item[1]["price"])
    return deals


def render_index(all_results: dict[str, list[dict]], last_updated: str, hist_avg: dict[str, float | None]) -> None:
    regions = list(all_results.keys())
    intl_tabs = INTERNATIONAL_REGIONS
    intl_json = json.dumps(intl_tabs)
    max_price_init = compute_max_price(all_results)
    deals = build_deal_board(all_results)

    global_airlines: set[str] = set()
    for flights in all_results.values():
        for flight in flights:
            if flight.get("airline"):
                global_airlines.add(flight["airline"])

    first_tab = html.escape(regions[0] if regions else "DFW")
    alpine_init = (
        f"{{ activeTab: '{first_tab}', maxPrice: {max_price_init}, airlineFilter: 'All', "
        f"showFilters: false, intlTabs: {intl_json}, showScrollTop: false }}"
    )

    lines = get_base_html_head(
        "Fli-Tracker | Multi-Destination Flight Search",
        "Daily curated flights from SLC/PVU to DFW, California, Cancun, Europe, Japan, and more.",
    )
    lines.extend(
        [
            "    <nav class='bg-white shadow-sm border-b border-gray-100 sticky top-0 z-50'>",
            "        <div class='max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex flex-col sm:flex-row justify-between items-center gap-3'>",
            "            <div class='nav-logo'>Fli-Tracker</div>",
            "            <div class='flex items-center gap-4 sm:gap-6'>",
            "                <a href='heatmap.html' class='text-xs sm:text-sm font-bold uppercase tracking-wider text-gray-500 hover:opacity-80'>Heatmap</a>",
            "                <a href='history.html' class='text-xs sm:text-sm font-bold uppercase tracking-wider nav-link-accent'>Trends &rarr;</a>",
            "            </div>",
            "        </div>",
            "    </nav>",
            "    <section class='hero-section py-16 md:py-28 px-6'>",
            "        <div class='max-w-7xl mx-auto max-w-2xl'>",
            "            <p class='text-sm font-bold tracking-[3px] text-gray-500 uppercase mb-4'>Weekend Escapes &amp; Global Travel</p>",
            "            <h1 class='page-header text-left'>Track your next adventure.</h1>",
            "            <p class='hero-text'>Discover curated flights from SLC/PVU. Optimized for Chase Sapphire Preferred rewards.</p>",
            f"            <p class='text-sm text-gray-500 mb-6'>Last updated: {html.escape(last_updated)}</p>",
            "            <a href='#flights' class='dt-btn-primary'>View Flight Options</a>",
            "        </div>",
            "    </section>",
            f"    <section id='flights' class='py-12 md:py-20 px-6 max-w-5xl mx-auto scroll-mt-24' x-data=\"{alpine_init}\" @scroll.window='showScrollTop = window.scrollY > 400'>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>Flight Options for <span x-text='activeTab'></span></h3>",
            "            <p class='text-gray-500' x-text=\"intlTabs.includes(activeTab) ? 'Departure: Any Day | Return: 7–10 Days later' : 'Departure: Wed / Thu / Fri | Return: Sat or Sun before 4 PM'\"></p>",
            "        </div>",
        ]
    )

    if deals:
        lines.append("        <div class='mb-8 p-5 bg-white border border-gray-200 rounded-xl shadow-sm'>")
        lines.append("            <h4 class='text-xs font-bold uppercase tracking-wider text-gray-500 mb-3'>Best Deals Right Now</h4>")
        lines.append("            <div class='flex flex-wrap gap-2'>")
        for region_name, best in deals[:8]:
            price = int(best["price"])
            region_esc = html.escape(region_name)
            lines.append(
                f"                <button type='button' @click=\"activeTab = '{region_esc}'\" "
                f"class='deal-chip'>{region_esc} <strong>${price}</strong></button>"
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
            "            <a href='https://secure.chase.com/web/auth/dashboard#/dashboard/travel' target='_blank' rel='noopener' class='shrink-0 text-center btn-accent'>Go to Chase Travel</a>",
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
            f"class='tab-btn whitespace-nowrap border-b-2 transition-colors'>{region_esc}</button>"
        )
    lines.append("            </nav>")
    lines.append("        </div>")

    lines.extend(
        [
            "        <div class='flex justify-end mb-4'>",
            "            <button type='button' @click='showFilters = !showFilters' class='filter-toggle text-sm font-semibold text-gray-500 hover:text-gray-800 flex items-center gap-1 bg-white border border-gray-200 px-4 py-2 rounded-full shadow-sm'>",
            "                <span x-text=\"showFilters ? 'Hide Filters' : 'Show Filters'\"></span>",
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

    for region_name, flights_list in all_results.items():
        region_esc = html.escape(region_name)
        lines.append(f"                <div x-show=\"activeTab === '{region_esc}'\" x-cloak role='tabpanel'>")

        priced = priced_flights(flights_list)
        if not priced:
            lines.append(f"                    <div class='p-8 text-center text-gray-500'>No flights found for {region_esc}.</div>")
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

        for key, group_flights in sorted_groups:
            origin, dest, airline, price, out_date, ret_date = key
            airline_json = json.dumps(airline)
            price_int = int(price)
            pts = int((price_int * 100) / 1.25)
            earn = price_int * 5

            lines.append(
                f"                    <div x-show=\"(airlineFilter === 'All' || airlineFilter === {airline_json}) && {price_int} <= maxPrice\" x-cloak>"
            )
            lines.append("                    <div x-data='{ expanded: false }' class='hover:bg-gray-50 transition-colors'>")
            lines.append(
                "                        <div @click='expanded = !expanded' class='cursor-pointer p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between'>"
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
                        f"                                    <span class='text-xs font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700'>&darr;{drop_pct}% vs avg</span>"
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
            lines.append(f"                                    <div class='text-xs text-green-600 font-semibold'>+{earn:,} pts</div>")
            lines.append("                                </div>")
            lines.append(
                "                                <div class='accent-text' :class=\"expanded ? 'rotate-180' : ''\" style='transition: transform .3s'>"
            )
            lines.append(
                "                                    <svg xmlns='http://www.w3.org/2000/svg' class='h-6 w-6' fill='none' viewBox='0 0 24 24' stroke='currentColor'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/></svg>"
            )
            lines.append("                                </div>")
            lines.append("                            </div>")
            lines.append("                        </div>")
            lines.append(
                "                        <div x-show='expanded' x-collapse x-cloak class='p-6 md:p-8 bg-gray-50 border-t border-gray-100'>"
            )
            lines.append("                            <h3 class='text-[13px] font-bold text-gray-500 uppercase tracking-wider mb-4'>Available Times</h3>")
            lines.append("                            <div class='grid grid-cols-1 lg:grid-cols-2 gap-4'>")

            for flight in group_flights:
                url = html.escape(flight.get("url") or "#", quote=True)
                lines.append("                                <div class='flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-white border border-gray-200 rounded-lg'>")
                lines.append("                                    <div class='mb-4 sm:mb-0 space-y-2 text-[15px] text-gray-700'>")
                lines.append(
                    f"                                        <div><span class='inline-block w-24 font-medium text-gray-500'>Outbound:</span> {format_datetime(flight['out_dep'])}</div>"
                )
                lines.append(
                    f"                                        <div><span class='inline-block w-24 font-medium text-gray-500'>Return:</span> {format_datetime(flight['ret_arr'])}</div>"
                )
                lines.append("                                    </div>")
                lines.append(
                    f"                                    <a href='{url}' target='_blank' rel='noopener' class='dt-btn-primary w-full sm:w-auto text-center'>Select</a>"
                )
                lines.append("                                </div>")

            lines.append("                            </div>")
            lines.append("                        </div>")
            lines.append("                    </div>")
            lines.append("                    </div>")

        region_best = min(priced, key=lambda row: row["price"])
        lines.append("                    <div class='px-6 py-8'>")
        lines.append("                        <div class='flex items-start gap-4 p-6 rounded-xl bg-emerald-50 border border-emerald-200'>")
        lines.append("                            <div class='text-2xl'>&#127775;</div>")
        lines.append("                            <div>")
        lines.append(f"                                <div class='text-[13px] font-bold uppercase tracking-wider text-emerald-700 mb-1'>Best Value to {region_esc}</div>")
        lines.append(
            f"                                <div class='text-gray-800 font-semibold text-lg'>{format_date(region_best['out_date'])} &mdash; "
            f"{format_date(region_best['ret_date'])} &middot; {html.escape(region_best['airline'])} to {html.escape(region_best.get('destination', region_name))} "
            f"&middot; <span class='text-emerald-700 font-bold'>${int(region_best['price'])}</span></div>"
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
            "            class='fixed bottom-6 right-6 scroll-top-btn p-3 z-50' ",
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

    with open("public/index.html", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print("Report generated: public/index.html")


def render_heatmap(all_results: dict[str, list[dict]]) -> None:
    heatmap_data: dict[str, dict[str, dict]] = {}
    for region_name, flights in all_results.items():
        by_date: dict[str, dict] = {}
        for flight in priced_flights(flights):
            day = flight["out_date"]
            if day not in by_date or flight["price"] < by_date[day]["price"]:
                by_date[day] = flight
        heatmap_data[region_name] = by_date

    regions = list(all_results.keys())
    first = html.escape(regions[0] if regions else "DFW")
    data_json = json.dumps(heatmap_data)

    lines = get_base_html_head(
        "Fli-Tracker | Calendar Heatmap",
        "Visual calendar heatmap of best flight prices from SLC/PVU by destination region.",
    )
    lines.extend(
        [
            "    <nav class='bg-white shadow-sm border-b sticky top-0 z-50'>",
            "        <div class='max-w-7xl mx-auto px-4 py-3 flex justify-between items-center'>",
            "            <div class='nav-logo'>Fli-Tracker</div>",
            "            <a href='index.html' class='text-sm font-bold uppercase nav-link-accent'>&larr; Back to Flights</a>",
            "        </div>",
            "    </nav>",
            f"    <section class='py-12 px-6 max-w-5xl mx-auto' x-data=\"{{ activeRegion: '{first}', heatmapData: {data_json} }}\">",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>Calendar Heatmap</h3>",
            "            <p class='text-gray-500'>Best outbound price per day — <span x-text='activeRegion'></span></p>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll'>",
            "            <nav class='flex gap-4 min-w-max border-b border-gray-200 pb-1'>",
        ]
    )
    for region in regions:
        region_esc = html.escape(region)
        lines.append(
            f"                <button type='button' @click=\"activeRegion = '{region_esc}'\" "
            f":class=\"activeRegion === '{region_esc}' ? 'tab-active border-b-2' : 'tab-inactive'\" "
            f"class='tab-btn whitespace-nowrap'>{region_esc}</button>"
        )
    lines.extend(
        [
            "            </nav>",
            "        </div>",
            "        <template x-for='region in Object.keys(heatmapData)' :key='region'>",
            "            <div x-show='activeRegion === region' x-cloak class='card-container bg-white border border-gray-200 p-6 overflow-x-auto'>",
            "                <p class='text-gray-500 text-center py-12' x-show='Object.keys(heatmapData[region] || {}).length === 0'>No data for this region yet.</p>",
            "                <div class='grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3' x-show='Object.keys(heatmapData[region] || {}).length > 0'>",
            "                    <template x-for='[date, flight] in Object.entries(heatmapData[region] || {}).sort((a,b) => a[0].localeCompare(b[0]))' :key='date'>",
            "                        <div class='p-3 rounded-lg border text-center' :class=\"flight.price < 320 ? 'bg-emerald-500 text-white' : flight.price <= 500 ? 'bg-amber-400 text-white' : 'bg-rose-500 text-white'\">",
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
    with open("public/heatmap.html", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print("Heatmap generated: public/heatmap.html")


def render_history(all_results: dict[str, list[dict]]) -> None:
    db_path = "app/data/tracker.db"
    history: dict[str, dict[str, list]] = {region: {"labels": [], "prices": []} for region in all_results}

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for region_name in all_results:
            cursor.execute(
                """
                SELECT SUBSTR(searched_at, 1, 10) AS day, MIN(price) AS min_price
                FROM search_history
                WHERE destination = ?
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """,
                (region_name,),
            )
            rows = list(reversed(cursor.fetchall()))
            history[region_name]["labels"] = [format_chart_date(row[0]) for row in rows]
            history[region_name]["prices"] = [row[1] for row in rows]
        conn.close()

    regions = list(all_results.keys())
    first = html.escape(regions[0] if regions else "DFW")
    history_json = json.dumps(history)

    lines = get_base_html_head(
        "Fli-Tracker | Price History",
        "14-day price trends for flights from SLC/PVU by destination region.",
        extra_scripts=["    <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>"],
    )
    lines.extend(
        [
            "    <nav class='bg-white shadow-sm border-b sticky top-0 z-50'>",
            "        <div class='max-w-7xl mx-auto px-4 py-3 flex justify-between items-center'>",
            "            <div class='nav-logo'>Fli-Tracker</div>",
            "            <div class='flex gap-4'>",
            "                <a href='heatmap.html' class='text-sm font-bold uppercase text-gray-500'>Heatmap</a>",
            "                <a href='index.html' class='text-sm font-bold uppercase nav-link-accent'>&larr; Flights</a>",
            "            </div>",
            "        </div>",
            "    </nav>",
            f"    <section class='py-12 px-6 max-w-5xl mx-auto' x-data='historyPage()' x-init='init()'>",
            "        <div class='mb-8 text-center'>",
            "            <h3 class='text-3xl font-bold text-gray-800 mb-2'>14-Day Price Trends</h3>",
            "            <p class='text-gray-500'>Lowest fare for <span x-text='activeRegion'></span></p>",
            "        </div>",
            "        <div class='mb-6 overflow-x-auto tab-scroll'>",
            "            <nav class='flex gap-4 min-w-max border-b border-gray-200 pb-1'>",
        ]
    )
    for region in regions:
        region_esc = html.escape(region)
        lines.append(
            f"                <button type='button' @click=\"activeRegion = '{region_esc}'\" "
            f":class=\"activeRegion === '{region_esc}' ? 'tab-active border-b-2' : 'tab-inactive'\" "
            f"class='tab-btn whitespace-nowrap'>{region_esc}</button>"
        )
    lines.extend(
        [
            "            </nav>",
            "        </div>",
            "        <div class='card-container bg-white border border-gray-200 p-4 md:p-8' style='position:relative;height:50vh;min-height:300px'>",
            "            <canvas id='priceChart'></canvas>",
            "            <p class='absolute inset-0 flex items-center justify-center text-gray-500' x-show='!hasData' x-cloak>No history yet for this region.</p>",
            "        </div>",
            "    </section>",
            f"    <script>window.HISTORY_DATA = {history_json}; window.HISTORY_DEFAULT = {json.dumps(regions[0] if regions else 'DFW')};</script>",
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
            "                    this.chart = new Chart(canvas.getContext('2d'), {",
            "                        type: 'line',",
            "                        data: {",
            "                            labels: d.labels,",
            "                            datasets: [{ data: d.prices, borderColor: '#14B8A6', backgroundColor: 'rgba(20,184,166,0.12)', fill: true, tension: 0.4, borderWidth: 3 }]",
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
    with open("public/history.html", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
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
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)


if __name__ == "__main__":
    main()
