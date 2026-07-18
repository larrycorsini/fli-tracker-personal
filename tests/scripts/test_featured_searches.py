"""Unit tests for featured trip matching and digest formatting."""

from __future__ import annotations

from datetime import datetime

from alert_format import (
    featured_digest_subject,
    format_featured_digest_imessage,
    format_featured_digest_plain,
)
from featured_searches import (
    active_featured_searches,
    build_featured_payload,
    flatten_featured_for_alert,
    flight_matches_featured,
    format_featured_option,
    match_featured_from_results,
)

DFW_SPEC = {
    "id": "dfw-sep-23-26",
    "title": "DFW · Sep 23–26",
    "blurb": "Cheap direct",
    "region": "DFW",
    "origins": ["SLC", "PVU"],
    "destination": "DFW",
    "ret_date": "2026-09-26",
    "max_stops": "0",
    "out_windows": [
        {"date": "2026-09-23", "after_hour": 12},
        {"date": "2026-09-24", "before_hour": 12},
    ],
    "max_options": 6,
}


def _flight(**overrides):
    base = {
        "origin": "SLC",
        "destination": "DFW",
        "out_date": "2026-09-23",
        "ret_date": "2026-09-26",
        "price": 237,
        "airline": "Delta Air Lines",
        "out_dep": "2026-09-23T17:20:00",
        "ret_arr": "2026-09-26T09:27:00",
        "url": "https://www.google.com/travel/flights/booking?tfs=TEST",
    }
    base.update(overrides)
    return base


class TestFlightMatchesFeatured:
    def test_wed_afternoon_matches(self):
        assert flight_matches_featured(_flight(), DFW_SPEC)

    def test_wed_morning_rejected(self):
        assert not flight_matches_featured(_flight(out_dep="2026-09-23T08:00:00"), DFW_SPEC)

    def test_thu_early_matches(self):
        assert flight_matches_featured(
            _flight(out_date="2026-09-24", out_dep="2026-09-24T05:00:00"),
            DFW_SPEC,
        )

    def test_thu_afternoon_rejected(self):
        assert not flight_matches_featured(
            _flight(out_date="2026-09-24", out_dep="2026-09-24T15:00:00"),
            DFW_SPEC,
        )

    def test_wrong_destination_rejected(self):
        assert not flight_matches_featured(_flight(destination="LAX"), DFW_SPEC)


class TestMatchFromResults:
    def test_sorts_and_caps(self):
        rows = match_featured_from_results(
            {
                "DFW": [
                    _flight(price=275, out_date="2026-09-24", out_dep="2026-09-24T05:00:00"),
                    _flight(price=237),
                    _flight(
                        price=237, out_dep="2026-09-23T17:20:00", ret_arr="2026-09-26T14:14:00"
                    ),
                    _flight(price=400, origin="PVU", out_dep="2026-09-23T13:32:00"),
                ]
            },
            {**DFW_SPEC, "max_options": 2},
        )
        assert len(rows) == 2
        assert rows[0]["price"] == 237


class TestActiveFeatured:
    def test_drops_past_trips(self):
        active = active_featured_searches(when=datetime(2026, 9, 27))
        assert all(s["id"] != "dfw-sep-23-26" for s in active)

    def test_keeps_upcoming(self):
        active = active_featured_searches(when=datetime(2026, 7, 18))
        assert any(s["id"] == "dfw-sep-23-26" for s in active)


class TestPayloadAndAlert:
    def test_payload_best_price(self):
        opt_row = _flight()
        payload = build_featured_payload([(DFW_SPEC, [opt_row])])
        assert payload["searches"][0]["bestPrice"] == 237
        assert payload["searches"][0]["options"][0]["windowLabel"] == "Wed afternoon"

    def test_flatten_for_alert(self):
        payload = build_featured_payload([(DFW_SPEC, [_flight()])])
        deals = flatten_featured_for_alert(payload)
        assert len(deals) == 1
        assert deals[0]["price"] == 237
        assert deals[0]["title"] == "DFW · Sep 23–26"

    def test_imessage_omits_tfs(self):
        deals = flatten_featured_for_alert(build_featured_payload([(DFW_SPEC, [_flight()])]))
        msg = format_featured_digest_imessage(deals)
        assert "tfs=" not in msg
        assert "Watching" in msg
        assert "DFW · Sep 23–26 · $237" in msg
        assert "flights.larrycorsini.com/#featured-dfw-sep-23-26" in msg

    def test_plain_includes_booking(self):
        deals = flatten_featured_for_alert(build_featured_payload([(DFW_SPEC, [_flight()])]))
        msg = format_featured_digest_plain(deals)
        assert "tfs=TEST" in msg
        assert featured_digest_subject(deals) == "Fli-Tracker: DFW · Sep 23–26 from $237"

    def test_format_option_thu_label(self):
        opt = format_featured_option(
            _flight(out_date="2026-09-24", out_dep="2026-09-24T05:00:00"),
            DFW_SPEC,
        )
        assert opt["windowLabel"] == "Thu morning"
