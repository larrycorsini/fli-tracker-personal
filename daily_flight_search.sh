#!/bin/bash
# Fli-Tracker daily flight search
# Runs at 6:00 AM via launchd (com.larry.fli-tracker.daily-search)

set -euo pipefail

PROJECT="/Users/larry/Documents/Projects/Fli-tracker"
LOG_DIR="$PROJECT/logs"
LOG_FILE="$LOG_DIR/daily_flight_search.log"
UV="${UV:-$(command -v uv)}"
NPX="${NPX:-$(command -v npx)}"

mkdir -p "$LOG_DIR"
cd "$PROJECT" || exit 1

exec >>"$LOG_FILE" 2>&1

echo "=== Fli-Tracker run at $(date) ==="

if [[ -z "$UV" ]]; then
  echo "ERROR: uv not found on PATH"
  exit 1
fi

SEARCH_OK=0
"$UV" run python find_direct.py && SEARCH_OK=1 || echo "ERROR: find_direct.py failed"

if [[ "$SEARCH_OK" -eq 1 ]]; then
  "$UV" run python alert.py || echo "WARN: alert.py failed (non-fatal)"
  "$UV" run python generate_flight_report.py || {
    echo "ERROR: generate_flight_report.py failed"
    exit 1
  }
  if [[ -n "$NPX" ]]; then
    "$NPX" netlify-cli deploy --prod --dir=public || {
      echo "ERROR: Netlify deploy failed"
      exit 1
    }
  else
    echo "WARN: npx not found — skipping Netlify deploy"
  fi
else
  echo "ERROR: Skipping report generation and deploy due to search failure"
  exit 1
fi

echo "=== Done at $(date) ==="
