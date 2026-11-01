"""Tests for tracker_config seasonal and heatmap helpers."""

from __future__ import annotations

from datetime import datetime

from tracker_config import (
    DOMESTIC_TRIP_DURATIONS,
    INTERNATIONAL_TRIP_DURATIONS,
    ORIGINS,
    REGIONS,
    heatmap_tier,
    planner_track_url,
    region_active,
    region_adults,
    region_origins,
    region_trip_durations,
)


class TestRegionActive:
    def test_cancun_winter_active(self):
        assert region_active("Cancun", datetime(2026, 1, 15)) is True

    def test_cancun_summer_inactive(self):
        assert region_active("Cancun", datetime(2026, 7, 15)) is False

    def test_dfw_always_active(self):
        assert region_active("DFW", datetime(2026, 7, 15)) is True


class TestHeatmapTier:
    def test_domestic_low(self):
        assert heatmap_tier(250, "DFW") == "low"

    def test_international_high(self):
        assert heatmap_tier(1200, "Europe") == "high"


class TestPlannerTrackUrl:
    def test_builds_query_link(self):
        url = planner_track_url("SLC", "DFW", "2026-07-01", "2026-07-04")
        assert "flights.larrycorsini.com" in url
        assert "watch=" in url
        assert "localhost" not in url


class TestRegionSearchOverrides:
    def test_seattle_is_slc_nonstop_two_adults(self):
        config = REGIONS["Seattle"]
        assert config["destinations"] == ["SEA"]
        assert config["max_stops"] == "0"
        assert config["adults"] == 2
        assert region_origins(config) == ["SLC"]
        assert region_adults(config) == 2
        assert region_trip_durations(config) == [3, 4, 2]

    def test_defaults_match_global_origins_and_durations(self):
        config = REGIONS["DFW"]
        assert region_origins(config) == ORIGINS
        assert region_adults(config) == 1
        assert region_trip_durations(config) == DOMESTIC_TRIP_DURATIONS
        europe = REGIONS["Europe"]
        assert region_trip_durations(europe) == INTERNATIONAL_TRIP_DURATIONS

    def test_invalid_adults_falls_back_to_one(self):
        assert region_adults({"adults": "two"}) == 1
        assert region_adults({"adults": 0}) == 1
