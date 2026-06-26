"""Unit tests for find_deals.py premium discovery helpers (offline)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIND_DEALS_PATH = REPO_ROOT / "find_deals.py"


def _load_find_deals():
    spec = importlib.util.spec_from_file_location("find_deals", FIND_DEALS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["find_deals"] = module
    spec.loader.exec_module(module)
    return module


find_deals = _load_find_deals()


class TestDestinationsForRun:
    def test_test_mode_limits_destinations(self):
        dests = find_deals.destinations_for_run(is_test=True)
        assert len(dests) <= find_deals.PREMIUM_DESTINATIONS_PER_RUN_TEST
        assert all("airport" in d for d in dests)

    def test_full_run_returns_batch(self):
        dests = find_deals.destinations_for_run(is_test=False)
        assert 1 <= len(dests) <= find_deals.PREMIUM_DESTINATIONS_PER_RUN


class TestPriceThreshold:
    def test_domestic_business_threshold(self):
        assert find_deals.price_threshold("domestic", "BUSINESS") == 800

    def test_international_premium_economy_threshold(self):
        assert find_deals.price_threshold("international", "PREMIUM_ECONOMY") == 1200

    def test_passes_threshold(self):
        assert find_deals.passes_threshold(750, "domestic", "BUSINESS") is True
        assert find_deals.passes_threshold(850, "domestic", "BUSINESS") is False
        assert find_deals.passes_threshold(None, "domestic", "BUSINESS") is False


class TestRankDeals:
    def test_sorts_by_price_and_caps_per_dest(self, monkeypatch):
        monkeypatch.setattr(find_deals, "PREMIUM_MAX_DEALS_PER_DEST", 2)
        monkeypatch.setattr(find_deals, "PREMIUM_GLOBAL_TOP_N", 10)
        deals = [
            {"airport": "LHR", "cabin": "Business", "price": 1900},
            {"airport": "LHR", "cabin": "Business", "price": 1800},
            {"airport": "LHR", "cabin": "Business", "price": 1700},
            {"airport": "CDG", "cabin": "Business", "price": 1500},
        ]
        ranked = find_deals.rank_deals(deals)
        assert ranked[0]["price"] == 1500
        lhr = [d for d in ranked if d["airport"] == "LHR"]
        assert len(lhr) == 2


class TestMergeRotatedResults:
    def test_replaces_searched_destinations_only(self):
        prior = [
            {"airport": "LHR", "cabin": "Business", "price": 2000},
            {"airport": "CDG", "cabin": "Business", "price": 1600},
        ]
        new = [{"airport": "LHR", "cabin": "Business", "price": 1700}]
        merged = find_deals.merge_rotated_results(prior, new, {"LHR"})
        airports = {d["airport"] for d in merged}
        assert "CDG" in airports
        lhr = [d for d in merged if d["airport"] == "LHR"]
        assert len(lhr) == 1
        assert lhr[0]["price"] == 1700


class TestLoadPrior:
    def test_load_prior_validates_deals_list(self, tmp_path, monkeypatch):
        path = tmp_path / "premium_deals.json"
        path.write_text(
            json.dumps(
                {
                    "deals": [{"airport": "LHR", "price": 1500}, "bad"],
                    "searched_destinations": ["LHR"],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(find_deals, "PREMIUM_DEAL_OUTPUT_JSON", str(path))
        loaded = find_deals._load_prior()
        assert len(loaded["deals"]) == 1
        assert loaded["deals"][0]["airport"] == "LHR"


class TestEstimateApiCalls:
    def test_estimate_within_budget(self):
        calls = find_deals.estimate_api_calls(12, is_test=False)
        assert 50 <= calls <= 80

    def test_test_mode_fewer_calls(self):
        test_calls = find_deals.estimate_api_calls(3, is_test=True)
        full_calls = find_deals.estimate_api_calls(3, is_test=False)
        assert test_calls < full_calls


class TestDatePairsFromResults:
    def test_filters_above_threshold(self):
        class FakeDatePrice:
            def __init__(self, out, ret, price):
                self.date = (out, ret)
                self.price = price

        results = [
            FakeDatePrice(datetime(2026, 7, 1), datetime(2026, 7, 8), 750.0),
            FakeDatePrice(datetime(2026, 7, 2), datetime(2026, 7, 9), 950.0),
        ]
        pairs = find_deals._date_pairs_from_results(
            results, "SLC", "JFK", "domestic", "BUSINESS"
        )
        assert len(pairs) == 1
        assert pairs[0][2] == "2026-07-01"
