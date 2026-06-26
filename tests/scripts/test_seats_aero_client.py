"""Unit tests for seats_aero_client.py (mocked HTTP — no live API)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATH = REPO_ROOT / "seats_aero_client.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("seats_aero_client", CLIENT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["seats_aero_client"] = module
    spec.loader.exec_module(module)
    return module


client = _load_client()

SAMPLE_RESPONSE = {
    "data": [
        {
            "Date": "2026-08-15",
            "Source": "alaska",
            "Route": {"OriginAirport": "SLC", "DestinationAirport": "LHR"},
            "JAvailable": True,
            "JMileageCost": "32500",
            "JAirlines": "BA",
            "WAvailable": True,
            "WMileageCost": "22000",
            "WAirlines": "VS",
        },
        {
            "Date": "2026-08-20",
            "Source": "united",
            "Route": {"OriginAirport": "PVU", "DestinationAirport": "LHR"},
            "JAvailable": True,
            "JMileageCost": "40000",
            "JAirlines": "UA",
            "WAvailable": False,
            "WMileageCost": "0",
            "WAirlines": "",
        },
    ],
    "count": 2,
    "hasMore": False,
}


class _MockResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self) -> dict:
        return self._payload


class _MockHttpxClient:
    def __init__(self, *args, **kwargs):
        self.last_request: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None, headers=None):
        self.last_request = {"url": url, "params": params, "headers": headers}
        return _MockResponse(SAMPLE_RESPONSE)


@pytest.fixture
def usage_file(tmp_path, monkeypatch):
    path = tmp_path / "seats_aero_usage.json"
    monkeypatch.setattr(client, "USAGE_PATH", path)
    return path


@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("SEATS_AERO_API_KEY", "test-key-redacted")
    monkeypatch.delenv("SEATS_AERO_DISABLED", raising=False)


class TestIsEnabled:
    def test_disabled_without_key(self, monkeypatch):
        monkeypatch.delenv("SEATS_AERO_API_KEY", raising=False)
        assert client.is_enabled() is False

    def test_enabled_with_key(self, api_env):
        assert client.is_enabled() is True

    def test_explicit_disable_flag(self, api_env, monkeypatch):
        monkeypatch.setenv("SEATS_AERO_DISABLED", "true")
        assert client.is_enabled() is False


class TestCachedSearch:
    def test_parses_business_and_premium_rows(self, api_env, usage_file, monkeypatch):
        mock = _MockHttpxClient()
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: mock)
        client.begin_run()
        rows = client.cached_search_destination(
            ["SLC", "PVU"],
            "LHR",
            "2026-08-01",
            "2026-08-31",
        )
        assert len(rows) == 3
        business = [r for r in rows if r.cabin == "BUSINESS"]
        assert business[0].points_one_way == 32500
        assert business[0].mileage_program == "alaska"
        assert mock.last_request is not None
        assert mock.last_request["headers"]["Partner-Authorization"] == "test-key-redacted"
        assert mock.last_request["params"]["cabins"] == "business,premium"

    def test_round_trip_estimate_doubles_one_way(self, api_env, usage_file, monkeypatch):
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: _MockHttpxClient())
        client.begin_run()
        rows = client.cached_search_destination(
            ["SLC"], "LHR", "2026-08-01", "2026-08-31", cabins=("BUSINESS",)
        )
        assert rows[0].points_round_trip_estimate == 65000

    def test_skips_when_daily_budget_exhausted(self, api_env, usage_file, monkeypatch):
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        usage_file.write_text(
            json.dumps({"utc_date": client._utc_today(), "daily_count": 950, "run_count": 0}),
            encoding="utf-8",
        )
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: _MockHttpxClient())
        rows = client.cached_search_destination(["SLC"], "LHR", "2026-08-01", "2026-08-31")
        assert rows == []

    def test_skips_when_run_limit_reached(self, api_env, usage_file, monkeypatch):
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        usage_file.write_text(
            json.dumps({"utc_date": client._utc_today(), "daily_count": 0, "run_count": 10}),
            encoding="utf-8",
        )
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: _MockHttpxClient())
        rows = client.cached_search_destination(["SLC"], "LHR", "2026-08-01", "2026-08-31")
        assert rows == []

    def test_increments_usage_counter(self, api_env, usage_file, monkeypatch):
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: _MockHttpxClient())
        client.begin_run()
        client.cached_search_destination(["SLC"], "LHR", "2026-08-01", "2026-08-31")
        saved = json.loads(usage_file.read_text(encoding="utf-8"))
        assert saved["daily_count"] == 1
        assert saved["run_count"] == 1


class TestLookupAward:
    def test_finds_matching_origin_date_cabin(self, api_env, usage_file, monkeypatch):
        monkeypatch.setattr(client.httpx, "Client", lambda *a, **k: _MockHttpxClient())
        client.begin_run()
        rows = client.cached_search_destination(
            ["SLC", "PVU"], "LHR", "2026-08-01", "2026-08-31"
        )
        match = client.lookup_award(
            rows, origin="SLC", dest="LHR", out_date="2026-08-15", cabin="BUSINESS"
        )
        assert match is not None
        assert match.points_one_way == 32500

    def test_returns_none_when_no_match(self):
        row = client.AwardAvailability(
            origin="SLC",
            destination="LHR",
            out_date="2026-08-15",
            cabin="BUSINESS",
            points_one_way=30000,
            mileage_program="alaska",
            airlines="BA",
        )
        assert (
            client.lookup_award(
                [row], origin="SLC", dest="LHR", out_date="2026-09-01", cabin="BUSINESS"
            )
            is None
        )
