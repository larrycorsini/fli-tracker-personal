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


class TestDurationsForRun:
    def test_test_mode_limits_durations(self):
        durations = find_deals.durations_for_run(is_test=True)
        assert len(durations) <= find_deals.PREMIUM_TRIP_DURATIONS_PER_RUN_TEST
        assert all(isinstance(d, int) for d in durations)

    def test_full_run_returns_rotated_batch(self):
        durations = find_deals.durations_for_run(is_test=False)
        assert 1 <= len(durations) <= find_deals.PREMIUM_TRIP_DURATIONS_PER_RUN


class TestPriceThreshold:
    def test_domestic_business_threshold(self):
        assert find_deals.price_threshold("domestic", "BUSINESS") == 1400

    def test_international_premium_economy_threshold(self):
        assert find_deals.price_threshold("international", "PREMIUM_ECONOMY") == 2000

    def test_passes_threshold(self):
        assert find_deals.passes_threshold(1300, "domestic", "BUSINESS") is True
        assert find_deals.passes_threshold(1500, "domestic", "BUSINESS") is False
        assert find_deals.passes_threshold(None, "domestic", "BUSINESS") is False


class TestPointsThreshold:
    def test_domestic_business_points_threshold(self):
        assert find_deals.points_threshold("domestic", "BUSINESS") == 100_000

    def test_estimate_chase_points(self):
        assert find_deals.estimate_chase_points(1250) == 100_000
        assert find_deals.estimate_chase_points(None) is None

    def test_passes_deal_threshold_cash_or_points(self):
        assert find_deals.passes_deal_threshold(1300, 104_000, "domestic", "BUSINESS") is True
        assert find_deals.passes_deal_threshold(None, 90_000, "domestic", "BUSINESS") is True
        assert find_deals.passes_deal_threshold(1500, 130_000, "domestic", "BUSINESS") is False


class TestPaymentType:
    def test_cash_with_chase_estimate(self):
        assert find_deals.payment_type_for_deal(800.0, 64_000, points_from_award=False) == "both"

    def test_award_only(self):
        assert find_deals.payment_type_for_deal(None, 80_000, points_from_award=True) == "points"

    def test_both_award_and_cash(self):
        assert find_deals.payment_type_for_deal(900.0, 70_000, points_from_award=True) == "both"


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

    def test_cash_with_booking_url_ranks_before_points(self):
        deep = "https://www.google.com/travel/flights/booking?tfs=ABC"
        deals = [
            {
                "airport": "PHX",
                "cabin": "Business",
                "price": None,
                "points": 18000,
                "google_flights_url": "https://www.google.com/travel/flights?q=PHX",
            },
            {"airport": "SAN", "cabin": "Business", "price": 359, "booking_url": deep},
        ]
        ranked = find_deals.rank_deals(deals)
        assert ranked[0]["airport"] == "SAN"
        assert ranked[0]["booking_url"] == deep


class TestDealSortHelpers:
    def test_is_valid_deep_booking_url(self):
        assert find_deals.is_valid_deep_booking_url(
            "https://www.google.com/travel/flights/booking?tfs=ABC"
        )
        assert not find_deals.is_valid_deep_booking_url(
            "https://www.google.com/travel/flights?q=SLC"
        )
        assert not find_deals.is_valid_deep_booking_url("")

    def test_deal_rank_tier_prefers_bookable_cash(self):
        deep = "https://www.google.com/travel/flights/booking?tfs=ABC"
        cash_bookable = {"price": 400, "booking_url": deep}
        cash_no_link = {"price": 300, "booking_url": ""}
        points_only = {"points": 50000, "google_flights_url": "https://example.com/gf"}
        assert find_deals.deal_rank_tier(cash_bookable) < find_deals.deal_rank_tier(points_only)
        assert find_deals.deal_rank_tier(cash_bookable) < find_deals.deal_rank_tier(cash_no_link)


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
        calls = find_deals.estimate_api_calls(10, is_test=False)
        assert 70 <= calls <= 100

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
            FakeDatePrice(datetime(2026, 7, 1), datetime(2026, 7, 8), 1300.0),
            FakeDatePrice(datetime(2026, 7, 2), datetime(2026, 7, 9), 1500.0),
        ]
        pairs = find_deals._date_pairs_from_results(
            results, "SLC", "JFK", "domestic", "BUSINESS", 7
        )
        assert len(pairs) == 1
        assert pairs[0][2] == "2026-07-01"
        assert pairs[0][5] == 7


class TestSeatsAeroAwardLookup:
    def test_fetch_award_from_cache_doubles_one_way(self):
        row = find_deals.AwardAvailability(
            origin="SLC",
            destination="LHR",
            out_date="2026-08-15",
            cabin="BUSINESS",
            points_one_way=32500,
            mileage_program="alaska",
            airlines="BA",
        )
        points, program = find_deals._fetch_seats_aero_award(
            "SLC",
            "LHR",
            "2026-08-15",
            "2026-08-22",
            "BUSINESS",
            award_cache=[row],
        )
        assert points == 65000
        assert program == "alaska"

    def test_fetch_award_returns_none_without_cache(self):
        points, program = find_deals._fetch_seats_aero_award(
            "SLC", "LHR", "2026-08-15", "2026-08-22", "BUSINESS", award_cache=None
        )
        assert points is None
        assert program is None


class TestAwardOnlyDeals:
    def test_creates_points_only_deal_under_threshold(self):
        row = find_deals.AwardAvailability(
            origin="SLC",
            destination="LHR",
            out_date="2026-08-15",
            cabin="BUSINESS",
            points_one_way=40000,
            mileage_program="united",
            airlines="UA",
        )
        dest_info = {
            "airport": "LHR",
            "label": "London",
            "region_label": "Europe",
            "type": "international",
        }
        deals = find_deals._award_only_deals_from_cache(dest_info, [row], [7], existing_keys=set())
        assert len(deals) == 1
        assert deals[0]["price"] is None
        assert deals[0]["points"] == 80000
        assert deals[0]["points_source"] == "seats_aero"
        assert deals[0]["mileage_program"] == "united"
        assert deals[0]["paymentType"] == "points"
        assert deals[0]["hasCashPrice"] is False
        assert deals[0]["isRoundTrip"] is True
        assert deals[0]["booking_url"] == ""
        assert deals[0]["google_flights_url"].startswith("https://www.google.com/travel/flights")
        assert "SLC" in deals[0]["google_flights_url"]
        assert "LHR" in deals[0]["google_flights_url"]
