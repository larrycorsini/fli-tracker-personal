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
                    "booking_url": "https://example.com/dfw",
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
                    "booking_url": "https://example.com/lhr",
                },
            ],
        }
        payload = report.build_premium_deals_payload(raw, "Fri, Jun 26, 2026 at 09:00 AM")
        assert payload["deals"][0]["isDomestic"] is True
        assert payload["deals"][0]["stops"] == 0
        assert payload["deals"][0]["outDateFmt"] == "Thu, Aug 06"
        assert payload["deals"][1]["isDomestic"] is False
        assert payload["deals"][1]["stops"] == 1

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
