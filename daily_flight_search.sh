#!/bin/bash
# Fli-Tracker daily flight search
# Runs at 6:00 AM via launchd (com.larry.fli-tracker.daily-search)
#
# iMessage alerts: set FLI_ALERT_PHONE in the launchd plist EnvironmentVariables
# (~/Library/LaunchAgents/com.larry.fli-tracker.daily-search.plist). Do not commit
# the phone number to the repo. Without it, alert.py skips alerts (non-fatal).
#
# Example plist keys (replace paths and phone with your values):
#   ProgramArguments: /bin/bash, /path/to/daily_flight_search.sh
#   EnvironmentVariables: FLI_ALERT_PHONE → +1XXXXXXXXXX
#   StartCalendarInterval: Hour=6, Minute=0
# Reload: launchctl unload ~/Library/LaunchAgents/com.larry.fli-tracker.daily-search.plist
#         launchctl load   ~/Library/LaunchAgents/com.larry.fli-tracker.daily-search.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$SCRIPT_DIR"
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
"$UV" run python find_direct.py --force && SEARCH_OK=1 || echo "ERROR: find_direct.py failed"

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
