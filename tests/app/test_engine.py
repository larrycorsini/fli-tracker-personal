"""Tests for app.engine search helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.engine import (
    FlightSearchOptions,
    _attach_booking_url,
    _merged_exclude_airlines,
    _serialize_flight,
)


class TestMergedExcludeAirlines:
    def test_default_exclusions(self):
        opts = FlightSearchOptions(apply_default_exclusions=True)
        merged = _merged_exclude_airlines(opts)
        assert merged is not None
        assert "F9" in merged
        assert "NK" in merged

    def test_disable_defaults(self):
        opts = FlightSearchOptions(apply_default_exclusions=False)
        assert _merged_exclude_airlines(opts) is None

    def test_extra_exclusions(self):
        opts = FlightSearchOptions(exclude_airlines=["DL"], apply_default_exclusions=True)
        merged = _merged_exclude_airlines(opts)
        assert merged is not None
        assert "DL" in merged
        assert "F9" in merged


class TestAttachBookingUrl:
    def test_prefers_deep_link(self):
        searcher = MagicMock()
        searcher.build_flight_booking_url.return_value = (
            "https://google.com/travel/flights/booking?tfs=abc"
        )
        flight_data: dict = {}
        opts = FlightSearchOptions()
        _attach_booking_url(
            searcher, object(), flight_data, "SLC", "DFW", "2026-07-01", "2026-07-04", opts
        )
        assert flight_data["booking_url"].startswith("https://google.com/travel/flights/booking")
        assert flight_data["url"] == flight_data["booking_url"]

    def test_fallback_when_build_fails(self):
        searcher = MagicMock()
        searcher.build_flight_booking_url.side_effect = RuntimeError("boom")
        flight_data: dict = {}
        opts = FlightSearchOptions()
        _attach_booking_url(searcher, object(), flight_data, "SLC", "DFW", "2026-07-01", None, opts)
        assert "google.com/travel/flights" in flight_data["url"]


class TestSerializeFlightNullPrice:
    def test_one_way_none_price_skipped(self):
        leg = MagicMock()
        leg.airline.name = "_AA"
        leg.flight_number = "100"
        leg.departure_datetime = None
        leg.arrival_datetime = None
        leg.departure_airport.name = "SLC"
        leg.arrival_airport.name = "DFW"
        flight = MagicMock()
        flight.price = None
        flight.currency = "USD"
        flight.legs = [leg]
        assert _serialize_flight(flight, False) is None


class TestBookingOptionsBridge:
    @pytest.mark.asyncio
    async def test_delegates_to_mcp_helper(self):
        from app.engine import get_booking_options_async

        mock_result = {"success": True, "options": [], "count": 0}
        with patch("fli.mcp.server._execute_booking_options", return_value=mock_result):
            result = await get_booking_options_async("SLC", "DFW", "2026-07-01", "2026-07-04")
        assert result["success"] is True
