# Requirements: Fli-Tracker — Milestone v1.1

**Defined:** 2026-05-30
**Core Value:** Tracker app keeps working while `fli` library stays current with upstream

## Milestone Requirements

### Cleanup

- [ ] **CLEAN-01**: `hot_core.py` moved to `app/hotels.py`; `app/engine.py` imports directly with no `sys.path` manipulation
- [ ] **CLEAN-02**: `flight_gui.py` archived (moved to `examples/archive/` or removed with README note); no broken references
- [ ] **CLEAN-03**: Dependent imports updated (`hotels_mcp.py`, `plan_trip.py`, `hot`, `test_hotels.py`) to use `app.hotels`

### App Testing

- [ ] **TEST-01**: `tests/app/` exists with FastAPI TestClient coverage for `/`, `/api/airports`, tracker CRUD, and search endpoints
- [ ] **TEST-02**: Engine unit tests cover flight/date serialization including null-price filtering (regression from v1.0 merge)
- [ ] **TEST-03**: Hotel search wrapper tested with mocked HTTP (no live Google Hotels calls in CI)
- [ ] **TEST-04**: `uv run pytest -vv --ignore=tests/search/` passes with all new app tests

### Booking Links

- [ ] **FEAT-01**: Flight search API responses include per-result `booking_url` built via `SearchFlights.build_flight_booking_url`
- [ ] **FEAT-02**: Date search API responses include `booking_url` deep links (route + date)
- [ ] **FEAT-03**: Web UI flight and date result cards render clickable "Book on Google Flights" links using API `booking_url`

### Quality & Ship

- [ ] **QA-01**: `make lint` passes with no new errors
- [ ] **PUSH-01**: `main` pushed to `personal` remote; v1.1 tag created and pushed after milestone completion

## Future Requirements

Deferred to later milestones.

### Features

- **FEAT-04**: Evaluate `fli-js` for frontend integration
- **FEAT-05**: Booking options API (`search_booking_options`) in tracker UI

### Cleanup

- **CLEAN-04**: Move `track_my_flight.py`, `plan_trip.py` into `examples/` or `scripts/`
- **CLEAN-05**: Consolidate `hotels_mcp.py` with app hotel module

## Out of Scope

| Feature | Reason |
|---------|--------|
| fli-js frontend rewrite | Separate evaluation milestone; Python static UI sufficient for v1.1 |
| Root script full cleanup | Only hot_core + flight_gui in scope |
| Live Google Flights/Hotels tests in CI | Remain flaky; use mocks for app tests |
| PyPI/npm publishing | Upstream release process |
| Upstream contribution PR | Personal fork focus |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLEAN-01 | Phase 5 | Pending |
| CLEAN-02 | Phase 5 | Pending |
| CLEAN-03 | Phase 5 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| FEAT-01 | Phase 7 | Pending |
| FEAT-02 | Phase 7 | Pending |
| FEAT-03 | Phase 7 | Pending |
| QA-01 | Phase 8 | Pending |
| PUSH-01 | Phase 8 | Pending |

**Coverage:**
- Milestone requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-30*
*Last updated: 2026-05-30 after roadmap creation*
