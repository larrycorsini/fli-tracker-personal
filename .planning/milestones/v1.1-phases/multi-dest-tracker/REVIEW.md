---
phase: multi-dest-tracker
reviewed: 2026-06-18T12:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - find_direct.py
  - generate_flight_report.py
  - alert.py
  - tracker_config.py
  - daily_flight_search.sh
findings:
  critical: 2
  warning: 9
  info: 3
  total: 14
status: issues_found
---

# Phase multi-dest-tracker: Code Review Report

**Reviewed:** 2026-06-18T12:00:00Z  
**Depth:** standard  
**Files Reviewed:** 5 (+ skim: `app/engine.py`, `public/sw.js`)  
**Status:** issues_found

## Summary

Reviewed the multi-destination daily search pipeline: two-phase `find_direct.py`, static report generator, iMessage alerts, shared config, and launchd shell wrapper. Core price-`None` guards in `find_direct.py` mirror `app/engine.py` patterns and are generally sound. Atomic JSON checkpointing in `find_direct.py` is implemented correctly.

The highest-severity issues are in `generate_flight_report.py`: `json.dumps` output with double quotes is embedded inside HTML `x-data="..."` attributes, producing malformed markup in deployed `public/index.html` and `public/heatmap.html` (verified in generated output). `alert.py` ships a hardcoded default phone number in source. Several reliability gaps remain around resume semantics, history deduplication, and pipeline exit codes.

## Critical Issues

### CR-01: Alpine `x-data` attributes break on embedded JSON double quotes

**File:** `generate_flight_report.py:258-260`, `generate_flight_report.py:287`, `generate_flight_report.py:536`

**Issue:** `intl_json` and `heatmap_data` are produced via `json.dumps()` (double-quoted strings) and interpolated into `x-data="{ ... }"` HTML attributes also delimited by double quotes. HTML parsers terminate the attribute at the first inner `"`, yielding truncated/invalid Alpine init expressions.

Deployed output confirms breakage:

```html
x-data="{ activeTab: 'DFW', ..., intlTabs: ["Cancun", ...
```

Heatmap is worse: the entire `heatmapData` JSON (including booking URLs) is inlined, so `x-data` terminates immediately after `heatmapData: {`.

**Impact:** `intlTabs` conditional copy on index may fail; heatmap page Alpine state is almost certainly broken. This is a functional defect, not merely style.

**Fix:**
```python
# Option A: single-quoted x-data wrapper + json.dumps for JS literals
alpine_init = (
    f"{{ activeTab: {json.dumps(regions[0] if regions else 'DFW')}, "
    f"maxPrice: {max_price_init}, airlineFilter: 'All', "
    f"showFilters: false, intlTabs: {intl_json}, showScrollTop: false }}"
)
lines.append(f"    <section ... x-data='{alpine_init}' ...>")

# Option B (preferred for large heatmap payloads): external script tag
lines.append(f"    <script>window.HEATMAP_DATA = {data_json};</script>")
lines.append("    <section ... x-data=\"{ activeRegion: 'DFW', get heatmapData() { return window.HEATMAP_DATA } }\">")
```

Use `json.dumps()` for all string values placed in JS contexts; reserve `html.escape()` for HTML text nodes only.

---

### CR-02: Hardcoded personal phone number as default alert recipient

**File:** `alert.py:12`

**Issue:** `PHONE_NUMBER = os.environ.get("FLI_ALERT_PHONE", "2108527746")` embeds a real phone number in committed source. Anyone with repo access sees it; misconfigured clones alert the wrong recipient; number is exposed in git history even if later removed.

**Fix:**
```python
PHONE_NUMBER = os.environ.get("FLI_ALERT_PHONE")
if not PHONE_NUMBER:
    raise SystemExit("FLI_ALERT_PHONE environment variable is required for alerts")
```

Document the env var in launchd plist / `daily_flight_search.sh` comments; never commit the value.

## Warnings

### WR-01: Resume skips regions with any cached flights (stale data)

**File:** `find_direct.py:374-380`

**Issue:** `if all_results[region_name] and not force` skips a region whenever the checkpoint JSON contains a non-empty list. Daily runs without `--force` never refresh regions that completed on a prior day, so prices and booking URLs go stale until manual `--force`.

**Fix:** Track per-region `searched_at` in checkpoint metadata and re-search when older than one day, or default daily pipeline to `--force` with merge logic, or compare JSON mtime to today's date before skipping.

---

### WR-02: Duplicate `search_history` rows on every report generation

**File:** `generate_flight_report.py:207-210`

**Issue:** `update_history()` unconditionally `INSERT`s a row per region on each `generate_flight_report.py` run. Re-running the report (or a failed deploy retry) multiple times the same day inserts duplicate rows. The 14-day average query uses `MIN(price)` per day, so duplicates do not skew the daily minimum, but they bloat the table and any future `AVG` queries.

**Fix:** Use `INSERT OR REPLACE` / upsert on `(destination, searched_at)` or check for existing row before insert (mirror `app/tracker.py` `log_search` patterns if available).

---

### WR-03: Partial search failures block deploy via exit code 1

**File:** `find_direct.py:427`, `daily_flight_search.sh:26-44`

**Issue:** `main()` returns exit code 1 when `_stats["errors"] > 0`, even if `best_direct.json` was checkpointed with usable partial results. `daily_flight_search.sh` treats non-zero exit as fatal and skips report generation and Netlify deploy.

**Fix:** Return 0 when at least one region has priced flights written; reserve exit 1 for total failure (no JSON / all regions empty). Or add `--allow-partial` flag for the daily job.

---

### WR-04: Non-atomic writes for HTML reports and alert state

**File:** `generate_flight_report.py:505-506`, `generate_flight_report.py:573-574`, `generate_flight_report.py:684-685`, `alert.py:35-37`

**Issue:** `public/*.html` and `last_alert.json` are written directly. A crash mid-write can leave truncated HTML deployed on next Netlify push, or lose alert dedup state. `find_direct.py` correctly uses `atomic_write_json`; report and alert do not.

**Fix:** Reuse `atomic_write_json` from `find_direct.py` (move to shared module) for JSON; write HTML to `*.tmp` then `os.replace`.

---

### WR-05: Incomplete AppleScript string escaping in iMessage sender

**File:** `alert.py:16-25`

**Issue:** Only `\` and `"` are escaped. Message body includes a literal newline (`\n` in f-string) and may include Unicode/API-sourced airport strings. Unescaped newlines or `"` in flight metadata can break the AppleScript string or alter message routing.

**Fix:** Prefer `subprocess.run(["osascript", "-"], input=script, text=True)` with a heredoc-style script, or pass the message via `quoted form of` in AppleScript:
```python
def send_imessage(phone_number: str, message: str) -> None:
    script = f'''
    on run argv
        set msg to item 1 of argv
        set phone to item 2 of argv
        tell application "Messages"
            set targetService to 1st service whose service type = iMessage
            set targetBuddy to buddy phone of targetService
            send msg to targetBuddy
        end tell
    end run
    '''
    subprocess.run(["osascript", "-e", script, message, phone_number], check=True)
```

---

### WR-06: Retry loop cannot distinguish transient empty from legitimate no-results

**File:** `find_direct.py:143-148`, `find_direct.py:290-295`

**Issue:** Both date and flight searches retry up to 3 times whenever `results` is falsy. Legitimate empty result sets (no matching fares) trigger the same backoff as transient API failures, wasting quota and delaying the pipeline. Conversely, HTTP 429/5xx that return empty after client-level retries are silently treated as "no flights" without incrementing a distinct rate-limit counter.

**Fix:** Distinguish `None` (parse/API failure) from `[]` (confirmed empty); only retry on exceptions or `None`. Log `SearchHTTPError.status_code` when available.

---

### WR-07: Hardcoded absolute project path in daily shell script

**File:** `daily_flight_search.sh:7`

**Issue:** `PROJECT="/Users/larry/Documents/Projects/Fli-tracker"` breaks if the repo moves or runs on another machine/CI without editing the script.

**Fix:** `PROJECT="$(cd "$(dirname "$0")" && pwd)"` so the script is relocatable.

---

### WR-08: Unguarded datetime parsing can crash report generation

**File:** `generate_flight_report.py:18-25`, `generate_flight_report.py:446-449`

**Issue:** `format_date`, `format_datetime`, and `format_chart_date` call `fromisoformat` / `strptime` without try/except. Corrupt or legacy JSON (missing `out_dep`, malformed timestamps) aborts the entire report step after a successful search, blocking deploy.

**Fix:** Wrap parsing in helpers that return a safe fallback (`"—"`) and log a warning, matching defensive patterns in `find_direct.py:_flight_matches`.

---

### WR-09: Resume loads region payloads without schema validation

**File:** `find_direct.py:353-356`

**Issue:** Checkpoint resume assigns `existing[region_name]` without verifying it is a `list[dict]`. A partially edited or corrupted `best_direct.json` (wrong type, missing keys) causes `AttributeError` on `.extend()` during phase 2, aborting the full multi-region run.

**Fix:**
```python
region_data = existing.get(region_name)
if isinstance(region_data, list):
    all_results[region_name] = region_data
else:
    log.warning("Ignoring invalid checkpoint for %s", region_name)
```

## Info

### IN-01: `flights_ok` stat incremented when all results filtered out

**File:** `find_direct.py:322-323`

**Issue:** `_stats["flights_ok"]` increments after processing API results even when every row fails `_flight_matches`, making summary logs misleading for debugging domestic time-window filters.

**Fix:** Increment only when `matches` is non-empty, or add a separate `flights_filtered` counter.

---

### IN-02: `region_key` computed but unused for deduplication

**File:** `alert.py:78-80`

**Issue:** `region_key = f"{region_name}:{lowest_price:.0f}"` is stored in `last_alerts` but dedup logic only checks `date` and `price`. Dead field adds confusion when reading alert state.

**Fix:** Remove `region_key` or use it as the dedup key if price-only dedup is insufficient.

---

### IN-03: Report generator keys off JSON contents, not `REGIONS` config

**File:** `generate_flight_report.py:181-188`, `generate_flight_report.py:689-693`

**Issue:** `load_results()` returns only regions present in `best_direct.json`. If config adds a new region before the next search, the report omits it entirely (no empty tab). Low risk while search and config deploy together, but config/report can drift silently.

**Fix:** Merge `REGIONS.keys()` with loaded JSON, defaulting missing regions to `[]`.

---

_Reviewed: 2026-06-18T12:00:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
