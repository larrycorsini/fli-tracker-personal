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
        assert "London" in msg
        assert "https://example.com/book" in msg
