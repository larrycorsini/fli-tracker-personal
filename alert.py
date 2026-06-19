"""Send iMessage alerts when regional flight prices drop below configured thresholds."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from urllib.parse import quote

from tracker_config import OUTPUT_JSON, REGIONS, SITE_URL
from tracker_io import atomic_write_json

PHONE_NUMBER = os.environ.get("FLI_ALERT_PHONE")
ALERT_LOG = "last_alert.json"


def send_imessage(phone_number: str, message: str) -> None:
    script = """
    on run argv
        set msg to item 1 of argv
        set phone to item 2 of argv
        tell application "Messages"
            set targetService to 1st service whose service type = iMessage
            set targetBuddy to buddy phone of targetService
            send msg to targetBuddy
        end tell
    end run
    """
    subprocess.run(["osascript", "-e", script, message, phone_number], check=True)


def load_last_alerts() -> dict:
    if os.path.exists(ALERT_LOG):
        with open(ALERT_LOG, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_last_alerts(data: dict) -> None:
    atomic_write_json(ALERT_LOG, data)


def _priced_flights(flights: list[dict]) -> list[dict]:
    return [f for f in flights if f.get("price") is not None]


def region_deep_link(region_name: str) -> str:
    """Deep link to the dashboard with the destination tab selected."""
    return f"{SITE_URL}/?tab={quote(region_name)}"


def _format_weekday_date(dt_str: str) -> str:
    if not dt_str:
        return "—"
    try:
        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return dt.strftime("%a, %b %d")
    except (ValueError, TypeError):
        return dt_str


def collect_deals_under_threshold(all_results: dict) -> list[dict]:
    """Return best priced flight per region when price is at or below alert threshold."""
    deals: list[dict] = []
    for region_name, flights in all_results.items():
        priced = _priced_flights(flights)
        if not priced:
            continue

        threshold = REGIONS.get(region_name, {}).get("alert_threshold")
        if threshold is None:
            continue

        best = min(priced, key=lambda row: row["price"])
        lowest_price = best["price"]
        if lowest_price > threshold:
            continue

        deals.append(
            {
                "region": region_name,
                "price": lowest_price,
                "threshold": threshold,
                "origin": best.get("origin", "SLC"),
                "destination": best.get("destination", region_name),
                "out_date": best.get("out_date", ""),
                "ret_date": best.get("ret_date", ""),
                "airline": best.get("airline", ""),
                "url": best.get("url") or "",
            }
        )

    deals.sort(key=lambda row: row["price"])
    return deals


def format_morning_digest(deals: list[dict]) -> str:
    """Build a single morning summary iMessage listing all regions under threshold."""
    if not deals:
        return ""

    lines = ["\U0001f6eb FLI-TRACKER Morning Deals", ""]
    for deal in deals:
        region = deal["region"]
        price = int(deal["price"])
        origin = deal["origin"]
        dest = deal["destination"]
        out_fmt = _format_weekday_date(deal["out_date"])
        ret_fmt = _format_weekday_date(deal["ret_date"])
        airline = deal.get("airline") or "—"
        book = deal.get("url") or region_deep_link(region)
        lines.append(
            f"• {region}: ${price} ({origin}\u2192{dest}, {out_fmt}\u2013{ret_fmt}, {airline})"
        )
        lines.append(f"  Book: {book}")

    default_tab = deals[0]["region"]
    lines.append("")
    lines.append(f"View all: {region_deep_link(default_tab)}")
    return "\n".join(lines)


def digest_already_sent(last_alerts: dict, today_str: str, deals: list[dict]) -> bool:
    """True when today's digest was already sent for the same deal set."""
    prior = last_alerts.get("_digest", {})
    if prior.get("date") != today_str:
        return False
    snapshot = sorted((d["region"], d["price"]) for d in deals)
    return prior.get("deals") == snapshot


def main() -> None:
    if not PHONE_NUMBER:
        print("FLI_ALERT_PHONE not set — skipping alerts.")
        return

    if not os.path.exists(OUTPUT_JSON):
        print("No flights data found.")
        return

    with open(OUTPUT_JSON, encoding="utf-8") as handle:
        all_results = json.load(handle)

    if isinstance(all_results, list):
        all_results = {"DFW": all_results}

    if not all_results:
        print("No flights available in data.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    last_alerts = load_last_alerts()
    deals = collect_deals_under_threshold(all_results)

    if not deals:
        for region_name, flights in all_results.items():
            priced = _priced_flights(flights)
            if not priced:
                continue
            threshold = REGIONS.get(region_name, {}).get("alert_threshold")
            if threshold is None:
                continue
            lowest = min(priced, key=lambda row: row["price"])["price"]
            print(f"{region_name}: ${lowest:.0f} above threshold ${threshold:.0f}")
        print("No alerts sent.")
        return

    if digest_already_sent(last_alerts, today_str, deals):
        print(f"Morning digest already sent today for {len(deals)} deal(s).")
        return

    message = format_morning_digest(deals)
    print(f"Sending morning digest ({len(deals)} region(s) under threshold)...")
    try:
        send_imessage(PHONE_NUMBER, message)
        last_alerts["_digest"] = {
            "date": today_str,
            "deals": sorted((d["region"], d["price"]) for d in deals),
        }
        for deal in deals:
            last_alerts[deal["region"]] = {"price": deal["price"], "date": today_str}
        save_last_alerts(last_alerts)
        print("Morning digest sent successfully.")
    except Exception as exc:
        print(f"Failed to send morning digest: {exc}")


if __name__ == "__main__":
    main()
