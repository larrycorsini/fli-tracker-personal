"""Send iMessage/email alerts when regional or premium flight prices hit thresholds."""

from __future__ import annotations

import json
import os
from datetime import datetime

from alert_format import (
    _morning_digest_cards,
    _premium_digest_cards,
    combine_alert_content,
    format_morning_digest_plain,
    format_morning_digest_imessage,
    format_premium_digest_plain,
    format_premium_digest_imessage,
    morning_digest_subject,
    premium_digest_subject,
    premium_deals_deep_link,
    region_deep_link,
)
from alert_notifiers import dispatch_alert
from tracker_config import (
    OUTPUT_JSON,
    PREMIUM_DEAL_MAX_POINTS,
    PREMIUM_DEAL_MAX_PRICE,
    PREMIUM_DEAL_OUTPUT_JSON,
    REGIONS,
)
from tracker_io import atomic_write_json

ALERT_LOG = "last_alert.json"


def load_last_alerts() -> dict:
    if os.path.exists(ALERT_LOG):
        with open(ALERT_LOG, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_last_alerts(data: dict) -> None:
    atomic_write_json(ALERT_LOG, data)


def _priced_flights(flights: list[dict]) -> list[dict]:
    return [f for f in flights if f.get("price") is not None]


def format_morning_digest(deals: list[dict]) -> str:
    """Plain-text morning digest (iMessage)."""
    return format_morning_digest_plain(deals)


def format_premium_digest(deals: list[dict]) -> str:
    """Plain-text premium digest (iMessage)."""
    return format_premium_digest_plain(deals)


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


def collect_premium_deals() -> list[dict]:
    """Return premium cabin deals at or below configured cash/points thresholds."""
    if not os.path.exists(PREMIUM_DEAL_OUTPUT_JSON):
        return []

    with open(PREMIUM_DEAL_OUTPUT_JSON, encoding="utf-8") as handle:
        payload = json.load(handle)

    deals_in = payload.get("deals", []) if isinstance(payload, dict) else []
    qualifying: list[dict] = []

    for deal in deals_in:
        if not isinstance(deal, dict):
            continue
        market = deal.get("type", "international")
        cabin = deal.get("cabin_class", "BUSINESS")
        max_cash = PREMIUM_DEAL_MAX_PRICE.get(market, {}).get(cabin)
        max_points = PREMIUM_DEAL_MAX_POINTS.get(market, {}).get(cabin)
        price = deal.get("price")
        points = deal.get("points")
        cash_ok = price is not None and max_cash is not None and price <= max_cash
        points_ok = points is not None and max_points is not None and points <= max_points
        if not cash_ok and not points_ok:
            continue
        qualifying.append(
            {
                "destination": deal.get("destination", deal.get("airport", "")),
                "airport": deal.get("airport", ""),
                "origin": deal.get("origin", "SLC"),
                "cabin_class": cabin,
                "price": price,
                "points": points,
                "out_date": deal.get("out_date", ""),
                "ret_date": deal.get("ret_date", ""),
                "value_score": deal.get("value_score", ""),
                "url": deal.get("booking_url") or deal.get("google_flights_url") or "",
            }
        )

    qualifying.sort(
        key=lambda row: (
            row["price"] if row.get("price") is not None else float("inf"),
            row.get("points") or float("inf"),
        )
    )
    return qualifying[:10]


def digest_already_sent(
    last_alerts: dict, today_str: str, deals: list[dict], key: str = "_digest"
) -> bool:
    """True when today's digest was already sent for the same deal set."""
    prior = last_alerts.get(key, {})
    if prior.get("date") != today_str:
        return False
    if key == "_digest":
        snapshot = sorted((d["region"], d["price"]) for d in deals)
    else:
        snapshot = sorted(
            (d.get("region") or d.get("destination", ""), d.get("price"), d.get("points"))
            for d in deals
        )
    return prior.get("deals") == snapshot


def main() -> None:
    if not os.environ.get("FLI_ALERT_PHONE") and not os.environ.get("FLI_ALERT_EMAIL"):
        print("FLI_ALERT_PHONE / FLI_ALERT_EMAIL not set — skipping alerts.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    last_alerts = load_last_alerts()
    sections: list[tuple[str, str, str, str, str]] = []

    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, encoding="utf-8") as handle:
            all_results = json.load(handle)
        if isinstance(all_results, list):
            all_results = {"DFW": all_results}
        economy_deals = collect_deals_under_threshold(all_results)
        if economy_deals:
            if not digest_already_sent(last_alerts, today_str, economy_deals, "_digest"):
                sections.append(
                    (
                        morning_digest_subject(economy_deals),
                        "Morning Deals",
                        format_morning_digest_plain(economy_deals),
                        format_morning_digest_imessage(economy_deals),
                        _morning_digest_cards(economy_deals),
                    )
                )
                last_alerts["_digest"] = {
                    "date": today_str,
                    "deals": sorted((d["region"], d["price"]) for d in economy_deals),
                }
                for deal in economy_deals:
                    last_alerts[deal["region"]] = {"price": deal["price"], "date": today_str}
        elif all_results:
            for region_name, flights in all_results.items():
                priced = _priced_flights(flights)
                if not priced:
                    continue
                threshold = REGIONS.get(region_name, {}).get("alert_threshold")
                if threshold is None:
                    continue
                lowest = min(priced, key=lambda row: row["price"])["price"]
                print(f"{region_name}: ${lowest:.0f} above threshold ${threshold:.0f}")

    premium_deals = collect_premium_deals()
    if premium_deals and not digest_already_sent(
        last_alerts, today_str, premium_deals, "_premium_digest"
    ):
        sections.append(
            (
                premium_digest_subject(premium_deals),
                "Premium Deals",
                format_premium_digest_plain(premium_deals),
                format_premium_digest_imessage(premium_deals),
                _premium_digest_cards(premium_deals),
            )
        )
        last_alerts["_premium_digest"] = {
            "date": today_str,
            "deals": sorted(
                (d.get("destination", ""), d.get("price"), d.get("points")) for d in premium_deals
            ),
        }

    if not sections:
        print("No alerts sent.")
        return

    subject, email_plain, imessage_plain, html = combine_alert_content(sections)
    print(f"Sending alert ({len(sections)} section(s))...")
    try:
        channels = dispatch_alert(
            email_plain,
            html=html or None,
            imessage=imessage_plain or None,
            subject=subject,
        )
        save_last_alerts(last_alerts)
        print(f"Alert sent via: {', '.join(channels) or 'configured channels'}")
    except Exception as exc:
        print(f"Failed to send alert: {exc}")


if __name__ == "__main__":
    main()
