# Phase 2 Summary: Library Verification

**Completed:** 2026-05-30

## Plan 02-01: CLI & MCP smoke tests

| Check | Result |
|-------|--------|
| `uv run fli flights JFK LAX 2026-06-15 --format json` | ✅ 121 results, includes `booking_url` |
| MCP unit tests (`test_mcp_server_unit`, `test_mcp_server`, `test_mcp_http`) | ✅ 63 passed |
| `fli.core.links` importable | ✅ |
| `fli.search._proto`, `_wire`, `_decoders` importable | ✅ |

## Plan 02-02: Engine compatibility fix

**Issue:** After upstream merge, `_search_flights_sync` returned 0 results.

**Cause:** Upstream `FlightResult` can have `price=None` for some itineraries. Sorting by price raised `TypeError: '<' not supported between instances of 'NoneType' and 'float'`, caught by the broad except → empty list.

**Fix:** `app/engine.py`
- Return `None` from `_serialize_flight` when price is missing
- Sort with `float("inf")` fallback for safety

**Verification:**
- `_search_flights_sync('JFK','LAX','2026-06-15')` → 120 priced results, cheapest $169
- `_search_dates_sync` → 10 date results

## Requirements satisfied

- LIB-01 ✅ CLI returns JSON flight results
- LIB-02 ✅ MCP tests pass
- LIB-03 ✅ `app/engine.py` search wrappers work
- LIB-04 ✅ `fli/core/links.py` and search helpers present

## Commit

- `fix(app): skip unpriced flight results after upstream merge`
