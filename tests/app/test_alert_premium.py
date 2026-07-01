"""Tests for alert_notifiers and premium alert helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_alert():
    spec = importlib.util.spec_from_file_location("alert", REPO_ROOT / "alert.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["alert"] = module
    spec.loader.exec_module(module)
    return module


alert = _load_alert()


class TestPremiumDedup:
    def test_collapses_duplicate_san_rows(self):
        deals = [
            {
                "destination": "San Diego",
                "airport": "SAN",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 359,
                "points": 28720,
                "out_date": "2026-07-29",
                "ret_date": "2026-08-05",
                "url": "https://example.com/a",
            },
            {
                "destination": "San Diego",
                "airport": "SAN",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 359,
                "points": 28720,
                "out_date": "2026-07-29",
                "ret_date": "2026-08-05",
                "url": "https://example.com/b",
            },
            {
                "destination": "Phoenix",
                "airport": "PHX",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": None,
                "points": 18000,
                "out_date": "2026-08-11",
                "ret_date": "2026-08-16",
                "url": "",
            },
        ]
        deduped = alert.dedupe_premium_for_alert(deals)
        assert len(deduped) == 2
        assert deduped[0]["airport"] == "SAN"
        assert deduped[1]["airport"] == "PHX"


class TestPremiumDigest:
    def test_format_premium_digest_includes_book_link(self):
        deals = [
            {
                "destination": "London",
                "airport": "LHR",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 3200,
                "points": None,
                "out_date": "2026-08-01",
                "ret_date": "2026-08-10",
                "url": "https://example.com/book",
            }
        ]
        msg = alert.format_premium_digest(deals)
        assert "Premium Deals" in msg
        assert "London · Business · $3,200" in msg
        assert "https://example.com/book" in msg
