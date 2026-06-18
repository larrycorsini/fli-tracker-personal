"""Unit tests for find_direct.py two-phase search helpers (offline)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIND_DIRECT_PATH = REPO_ROOT / "find_direct.py"


def _load_find_direct():
    spec = importlib.util.spec_from_file_location("find_direct", FIND_DIRECT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["find_direct"] = module
    spec.loader.exec_module(module)
    return module


find_direct = _load_find_direct()


class TestDomesticFilters:
    def test_domestic_date_pair_valid_wed_sat(self):
        out_dt = datetime(2026, 7, 1)  # Wed
        ret_dt = datetime(2026, 7, 4)  # Sat
        assert find_direct._domestic_date_pair_valid(out_dt, ret_dt) is True

    def test_domestic_date_pair_rejects_monday_outbound(self):
        out_dt = datetime(2026, 7, 6)  # Mon
        ret_dt = datetime(2026, 7, 11)  # Sat
        assert find_direct._domestic_date_pair_valid(out_dt, ret_dt) is False

    def test_domestic_time_valid_wed_afternoon(self):
        out_dep = datetime(2026, 7, 1, 14, 0)
        ret_arr = datetime(2026, 7, 4, 15, 0)
        assert find_direct._domestic_time_valid(out_dep, ret_arr) is True

    def test_domestic_time_valid_rejects_late_return(self):
        out_dep = datetime(2026, 7, 1, 14, 0)
        ret_arr = datetime(2026, 7, 4, 17, 0)
        assert find_direct._domestic_time_valid(out_dep, ret_arr) is False


class TestDatePairsFromResults:
    def test_skips_unpriced_and_invalid_domestic_pairs(self):
        class FakeDatePrice:
            def __init__(self, out, ret, price):
                self.date = (out, ret)
                self.price = price

        results = [
            FakeDatePrice(datetime(2026, 7, 1), datetime(2026, 7, 4), 199.0),
            FakeDatePrice(datetime(2026, 7, 6), datetime(2026, 7, 11), 150.0),
            FakeDatePrice(datetime(2026, 7, 2), datetime(2026, 7, 5), None),
        ]
        pairs = find_direct._date_pairs_from_results(results, "SLC", "DFW", "domestic")
        assert len(pairs) == 1
        assert pairs[0][:4] == ("SLC", "DFW", "2026-07-01", "2026-07-04")


class TestLoadCheckpoint:
    def test_load_checkpoint_validates_region_lists(self, tmp_path, monkeypatch):
        path = tmp_path / "best_direct.json"
        path.write_text(
            json.dumps(
                {
                    "DFW": [{"origin": "SLC", "price": 250}],
                    "California Coast": "bad",
                    "Georgia": [1, 2, 3],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(find_direct, "OUTPUT_JSON", str(path))
        loaded = find_direct._load_checkpoint(force=False)
        assert loaded["DFW"] == [{"origin": "SLC", "price": 250}]
        assert loaded["California Coast"] == []
        assert loaded["Georgia"] == []


class TestExitCode:
    def test_exit_success_with_partial_results_despite_errors(self):
        all_results = {"DFW": [{"price": 200}], "California Coast": []}
        find_direct._stats["errors"] = 2
        assert find_direct._compute_exit_code(all_results) == 0

    def test_exit_failure_when_errors_and_no_results(self):
        all_results = {name: [] for name in find_direct.REGIONS}
        find_direct._stats["errors"] = 1
        assert find_direct._compute_exit_code(all_results) == 1

    def test_exit_success_when_all_empty_but_no_errors(self):
        all_results = {name: [] for name in find_direct.REGIONS}
        find_direct._stats["errors"] = 0
        assert find_direct._compute_exit_code(all_results) == 0
