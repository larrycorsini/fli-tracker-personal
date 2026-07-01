"""Offline unit tests for alert.py digest formatting and deep links."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERT_PATH = REPO_ROOT / "alert.py"


def _load_alert():
    spec = importlib.util.spec_from_file_location("alert", ALERT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["alert"] = module
    spec.loader.exec_module(module)
    return module


alert = _load_alert()


class TestRegionDeepLink:
    def test_tab_query_param(self):
        link = alert.region_deep_link("California Coast")
        assert link == "https://flights.larrycorsini.com/?tab=California%20Coast"

    def test_cancun_tab(self):
        link = alert.region_deep_link("Cancun")
        assert link.endswith("?tab=Cancun")


class TestCollectDeals:
    def test_returns_regions_under_threshold_only(self):
        dfw_fare = {
            "price": 280,
            "origin": "SLC",
            "destination": "DFW",
            "out_date": "2026-07-01",
            "ret_date": "2026-07-04",
            "airline": "Delta",
            "url": "https://example.com/book",
        }
        ca_fare = {
            "price": 400,
            "origin": "SLC",
            "destination": "LAX",
            "out_date": "2026-07-02",
            "ret_date": "2026-07-05",
            "airline": "United",
            "url": "",
        }
        all_results = {"DFW": [dfw_fare], "California Coast": [ca_fare]}
        deals = alert.collect_deals_under_threshold(all_results)
        assert len(deals) == 1
        assert deals[0]["region"] == "DFW"
        assert deals[0]["price"] == 280

    def test_skips_unpriced(self):
        all_results = {"DFW": [{"price": None}]}
        assert alert.collect_deals_under_threshold(all_results) == []


class TestMorningDigest:
    def test_includes_booking_links_and_site_url(self):
        deals = [
            {
                "region": "DFW",
                "price": 280,
                "origin": "SLC",
                "destination": "DFW",
                "out_date": "2026-07-01",
                "ret_date": "2026-07-04",
                "airline": "Delta",
                "url": "https://google.com/flights/book",
            }
        ]
        msg = alert.format_morning_digest(deals)
        assert "Morning Deals" in msg
        assert "DFW · $280" in msg
        assert "Jul 1–4" in msg
        assert "https://google.com/flights/book" in msg
        assert "flights.larrycorsini.com/?tab=DFW" in msg
        assert "Book:" not in msg

    def test_empty_deals_returns_empty_string(self):
        assert alert.format_morning_digest([]) == ""


class TestDigestDedup:
    def test_same_deals_same_day(self):
        deals = [{"region": "DFW", "price": 280}]
        last = {"_digest": {"date": "2026-06-18", "deals": [("DFW", 280)]}}
        assert alert.digest_already_sent(last, "2026-06-18", deals) is True

    def test_different_price_not_sent(self):
        deals = [{"region": "DFW", "price": 260}]
        last = {"_digest": {"date": "2026-06-18", "deals": [("DFW", 280)]}}
        assert alert.digest_already_sent(last, "2026-06-18", deals) is False
