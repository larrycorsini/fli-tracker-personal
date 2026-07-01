"""Tests for tracker_config seasonal and heatmap helpers."""

from __future__ import annotations

from datetime import datetime

from tracker_config import heatmap_tier, planner_track_url, region_active


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
        assert "track=" in url
        assert "SLC" in url
