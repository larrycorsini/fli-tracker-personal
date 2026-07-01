"""Offline unit tests for generate_flight_report.py helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "generate_flight_report.py"


def _load_report():
    spec = importlib.util.spec_from_file_location("generate_flight_report", REPORT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_flight_report"] = module
    spec.loader.exec_module(module)
    return module


report = _load_report()


def _sample_flight(
    price: float,
    out: str = "2026-07-01",
    ret: str = "2026-07-04",
    airline: str = "Delta",
):
    return {
        "origin": "SLC",
        "destination": "DFW",
        "airline": airline,
        "price": price,
        "out_date": out,
        "ret_date": ret,
        "out_dep": f"{out}T14:00:00",
        "ret_arr": f"{ret}T15:00:00",
        "url": "https://example.com/book",
    }


class TestFormatDate:
    def test_weekday_abbrev_included(self):
        assert report.format_date("2026-07-01") == "Wed, Jul 01"

    def test_datetime_includes_weekday(self):
        assert report.format_datetime("2026-07-01T14:00:00").startswith("Wed,")

    def test_chart_date_weekday(self):
        assert report.format_chart_date("2026-07-01") == "Wed Jul 01"


class TestCapRegionFlights:
    def test_caps_groups_and_times(self, monkeypatch):
        monkeypatch.setattr(report, "MAX_FARE_GROUPS_PER_REGION", 2)
        monkeypatch.setattr(report, "MAX_TIMES_PER_GROUP", 1)
        flights = [
            _sample_flight(300, out="2026-07-01", ret="2026-07-04"),
            _sample_flight(300, out="2026-07-01", ret="2026-07-04", airline="Delta"),
            _sample_flight(250, out="2026-07-08", ret="2026-07-11"),
            _sample_flight(200, out="2026-07-15", ret="2026-07-18"),
            _sample_flight(150, out="2026-07-22", ret="2026-07-25"),
        ]
        # Same price/date group counts as one group; distinct date pairs are separate groups
        flights[1]["out_dep"] = "2026-07-01T16:00:00"
        capped = report.cap_region_flights(flights)
        groups = {(f["out_date"], f["ret_date"], f["price"]) for f in capped}
        assert len(groups) <= 2
        for key in groups:
            count = sum(1 for f in capped if (f["out_date"], f["ret_date"], f["price"]) == key)
            assert count <= 1


class TestExistingFlightsJson:
    def test_detects_nonempty_region_data(self, tmp_path, monkeypatch):
        path = tmp_path / "flights.json"
        path.write_text(
            json.dumps({"regionData": {"DFW": {"groupCount": 2, "groups": []}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(report, "FLIGHTS_JSON", str(path))
        assert report._existing_flights_json_has_data() is True

    def test_empty_region_data_returns_false(self, tmp_path, monkeypatch):
        path = tmp_path / "flights.json"
        path.write_text(
            json.dumps({"regionData": {"DFW": {"groupCount": 0, "groups": []}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(report, "FLIGHTS_JSON", str(path))
        assert report._existing_flights_json_has_data() is False


class TestBuildRegionGroups:
    def test_weekday_labels_in_groups(self):
        payload = report.build_region_groups([_sample_flight(280)], "DFW", {"DFW": 350})
        assert payload["groups"]
        group = payload["groups"][0]
        assert group["outDateFmt"].startswith("Wed,")
        assert group["retDateFmt"].startswith("Sat,")
        assert group["times"][0]["outDepFmt"].startswith("Wed,")


class TestBuildPremiumDealsPayload:
    def test_includes_is_domestic_and_stops(self):
        raw = {
            "origins": ["SLC"],
            "deals": [
                {
                    "destination": "Dallas",
                    "airport": "DFW",
                    "region_label": "US South",
                    "origin": "SLC",
                    "cabin": "Business",
                    "price": 650,
                    "out_date": "2026-08-06",
                    "ret_date": "2026-08-13",
                    "airline": "Delta",
                    "stops": 0,
                    "is_domestic": True,
                    "booking_url": "https://www.google.com/travel/flights/booking?tfs=DFW",
                },
                {
                    "destination": "London",
                    "airport": "LHR",
                    "region_label": "Europe",
                    "origin": "SLC",
                    "cabin": "Premium Economy",
                    "price": 1100,
                    "out_date": "2026-09-10",
                    "ret_date": "2026-09-17",
                    "airline": "British Airways",
                    "stops": 1,
                    "type": "international",
                    "booking_url": "https://www.google.com/travel/flights/booking?tfs=LHR",
                },
            ],
        }
        payload = report.build_premium_deals_payload(raw, "Fri, Jun 26, 2026 at 09:00 AM")
        assert payload["deals"][0]["isDomestic"] is True
        assert payload["deals"][0]["stops"] == 0
        assert payload["deals"][0]["hasCashPrice"] is True
        assert payload["deals"][0]["isRoundTrip"] is True
        assert payload["deals"][0]["booking_url"].startswith(
            "https://www.google.com/travel/flights/booking?tfs="
        )
        assert payload["deals"][0]["outDateFmt"] == "Thu, Aug 06"
        assert payload["deals"][1]["isDomestic"] is False
        assert payload["deals"][1]["stops"] == 1

    def test_includes_points_and_payment_type(self):
        raw = {
            "deals": [
                {
                    "destination": "Dallas",
                    "airport": "DFW",
                    "price": 650,
                    "points": 52000,
                    "paymentType": "both",
                    "trip_duration": 5,
                    "out_date": "2026-08-06",
                    "ret_date": "2026-08-11",
                }
            ]
        }
        payload = report.build_premium_deals_payload(raw, "now")
        deal = payload["deals"][0]
        assert deal["points"] == 52000
        assert deal["paymentType"] == "both"
        assert deal["tripDuration"] == 5

    def test_infers_domestic_from_airport(self):
        raw = {
            "deals": [
                {
                    "destination": "Chicago",
                    "airport": "ORD",
                    "price": 700,
                    "out_date": "2026-08-01",
                    "ret_date": "2026-08-08",
                }
            ]
        }
        payload = report.build_premium_deals_payload(raw, "now")
        assert payload["deals"][0]["isDomestic"] is True

    def test_builds_google_flights_url_for_points_only(self):
        raw = {
            "deals": [
                {
                    "destination": "Chicago",
                    "airport": "ORD",
                    "origin": "SLC",
                    "out_date": "2026-08-14",
                    "ret_date": "2026-08-17",
                    "price": None,
                    "points": 30000,
                    "hasCashPrice": False,
                    "isRoundTrip": True,
                    "google_flights_url": "",
                }
            ]
        }
        payload = report.build_premium_deals_payload(raw, "now")
        deal = payload["deals"][0]
        assert deal["hasCashPrice"] is False
        assert deal["isRoundTrip"] is True
        assert deal["booking_url"] == ""
        assert deal["google_flights_url"].startswith("https://www.google.com/travel/flights")
        assert "SLC" in deal["google_flights_url"]
        assert "ORD" in deal["google_flights_url"]

    def test_cash_deep_link_only_in_booking_url(self):
        deep = "https://www.google.com/travel/flights/booking?tfs=ABC"
        raw = {
            "deals": [
                {
                    "destination": "San Diego",
                    "airport": "SAN",
                    "origin": "SLC",
                    "out_date": "2026-07-29",
                    "ret_date": "2026-08-05",
                    "price": 359,
                    "hasCashPrice": True,
                    "booking_url": deep,
                }
            ]
        }
        payload = report.build_premium_deals_payload(raw, "now")
        deal = payload["deals"][0]
        assert deal["booking_url"] == deep
        assert deal["google_flights_url"] == ""

    def test_cash_deals_rank_before_points_in_payload(self):
        deep = "https://www.google.com/travel/flights/booking?tfs=ABC"
        raw = {
            "deals": [
                {
                    "airport": "PHX",
                    "price": None,
                    "points": 18000,
                    "google_flights_url": "https://www.google.com/travel/flights?q=PHX",
                },
                {
                    "airport": "SAN",
                    "price": 359,
                    "booking_url": deep,
                    "hasCashPrice": True,
                },
            ]
        }
        payload = report.build_premium_deals_payload(raw, "now")
        assert payload["deals"][0]["airport"] == "SAN"

    def test_premium_section_never_uses_hash_fallback(self):
        section = "\n".join(report.render_premium_deals_section())
        assert 'deal.booking_url || "#"' not in section
        assert "deal.hasCashPrice && deal.booking_url" in section
        assert "Search on Google Flights" in section
        assert "Cash deals only" in section
