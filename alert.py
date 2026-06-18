"""Send iMessage alerts when regional flight prices drop below configured thresholds."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

from tracker_config import OUTPUT_JSON, REGIONS, SITE_URL

PHONE_NUMBER = os.environ.get("FLI_ALERT_PHONE", "2108527746")
ALERT_LOG = "last_alert.json"


def send_imessage(phone_number: str, message: str) -> None:
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    apple_script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{phone_number}" of targetService
        send "{escaped}" to targetBuddy
    end tell
    '''
    subprocess.run(["osascript", "-e", apple_script], check=True)


def load_last_alerts() -> dict:
    if os.path.exists(ALERT_LOG):
        with open(ALERT_LOG, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_last_alerts(data: dict) -> None:
    with open(ALERT_LOG, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _priced_flights(flights: list[dict]) -> list[dict]:
    return [f for f in flights if f.get("price") is not None]


def main() -> None:
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
    sent_any = False

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
            print(f"{region_name}: ${lowest_price:.0f} above threshold ${threshold:.0f}")
            continue

        region_key = f"{region_name}:{lowest_price:.0f}"
        prior = last_alerts.get(region_name, {})
        if prior.get("date") == today_str and prior.get("price") == lowest_price:
            print(f"{region_name}: alert already sent today for ${lowest_price:.0f}")
            continue

        dest = best.get("destination", region_name)
        msg = (
            f"\U0001f6eb FLI-TRACKER: {region_name} dropped to ${lowest_price:.0f} "
            f"({best['origin']}→{dest})!\nView: {SITE_URL}"
        )
        print(f"{region_name}: ${lowest_price:.0f} — sending alert...")
        try:
            send_imessage(PHONE_NUMBER, msg)
            last_alerts[region_name] = {"price": lowest_price, "date": today_str, "key": region_key}
            sent_any = True
        except Exception as exc:
            print(f"Failed to send alert for {region_name}: {exc}")

    if sent_any:
        save_last_alerts(last_alerts)
        print("Alerts sent successfully.")
    else:
        print("No alerts sent.")


if __name__ == "__main__":
    main()
