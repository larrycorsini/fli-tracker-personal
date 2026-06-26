#!/bin/bash
# Fli-Tracker daily flight search
# Runs at 6:00 AM via launchd (com.larry.fli-tracker.daily-search)
#
# Publish: after generate_flight_report.py, commits changed public/ report pages
# (index, heatmap, history, manifest) and pushes to remote `personal` branch `main`.
# Netlify is Git-linked and auto-deploys on push — no Netlify CLI required.
#
# Git push from launchd runs non-interactively. Ensure remote `personal` auth works
# without prompts: SSH URL + ssh-agent/deploy key, or HTTPS + osxkeychain helper.
# Check: git remote get-url personal
# Verify: GIT_TERMINAL_PROMPT=0 git push personal main --dry-run
#
# iMessage alerts: set FLI_ALERT_PHONE in the launchd plist EnvironmentVariables
# (~/Library/LaunchAgents/com.larry.fli-tracker.daily-search.plist). Do not commit
# the phone number to the repo. Without it, alert.py skips alerts (non-fatal).
#
# seats.aero awards (find_deals.py): launchd does NOT read .env — copy
# SEATS_AERO_API_KEY into the plist EnvironmentVariables (same block as FLI_ALERT_PHONE).
# For manual Terminal runs, use gitignored .env (see .env.example); python-dotenv loads it
# from the project root. After editing the plist: launchctl bootout/bootstrap (see below).
#
# Example plist keys (replace paths and phone with your values):
#   ProgramArguments: /Users/larry/.local/bin/fli-tracker-daily-search.sh
#   WorkingDirectory: /Users/larry/Projects/Fli-tracker
#   (launcher outside ~/Documents — macOS blocks launchd from exec'ing scripts in Documents)
#   EnvironmentVariables: FLI_ALERT_PHONE → +1XXXXXXXXXX
#                        SEATS_AERO_API_KEY → (your Pro API key)
#   StartCalendarInterval: Hour=6, Minute=0
# Reload: launchctl bootout gui/501/com.larry.fli-tracker.daily-search
#         launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.larry.fli-tracker.daily-search.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$SCRIPT_DIR"
LOG_DIR="$PROJECT/logs"
LOG_FILE="$LOG_DIR/daily_flight_search.log"
UV="${UV:-$(command -v uv)}"

mkdir -p "$LOG_DIR"
cd "$PROJECT" || exit 1

exec >>"$LOG_FILE" 2>&1

echo "=== Fli-Tracker run at $(date) ==="

if [[ -z "$UV" ]]; then
  echo "ERROR: uv not found on PATH"
  exit 1
fi

deploy_public_via_git() {
  local report_date remote_url
  report_date="$(date +%Y-%m-%d)"
  remote_url="$(git remote get-url personal 2>/dev/null || echo "personal (unknown)")"

  git add public/index.html public/heatmap.html public/history.html public/manifest.json public/data/flights.json public/data/premium-deals.json

  if git diff --staged --quiet; then
    echo "INFO: No public/ changes to commit — skipping git push"
    return 0
  fi

  if ! git commit -m "chore: daily flight report ${report_date}"; then
    echo "ERROR: git commit failed"
    return 1
  fi

  if ! git push personal main; then
    echo "ERROR: git push personal main failed — Netlify will not auto-deploy until push succeeds"
    echo "INFO: Remote personal URL: ${remote_url} (launchd needs non-interactive SSH or credential helper)"
    return 1
  fi

  echo "INFO: Pushed to personal/main — Netlify Git-linked site will publish public/"
  return 0
}

SEARCH_OK=0
"$UV" run python find_direct.py --force && SEARCH_OK=1 || echo "ERROR: find_direct.py failed"

if [[ "$SEARCH_OK" -eq 1 ]]; then
  DEALS_START=$(date +%s)
  "$UV" run python find_deals.py || echo "WARN: find_deals.py failed (non-fatal)"
  DEALS_ELAPSED=$(( $(date +%s) - DEALS_START ))
  echo "INFO: find_deals.py finished in ${DEALS_ELAPSED}s"
  "$UV" run python alert.py || echo "WARN: alert.py failed (non-fatal)"
  "$UV" run python generate_flight_report.py || {
    echo "ERROR: generate_flight_report.py failed"
    exit 1
  }
  deploy_public_via_git || echo "ERROR: Git deploy failed (search and report succeeded)"
else
  echo "ERROR: Skipping report generation and deploy due to search failure"
  exit 1
fi

echo "=== Done at $(date) ==="
