#!/bin/bash
# Runs Playwright tests locally. On failure, embeds the full log in a
# pipeline-failure dispatch to GitHub Actions — no Gist needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/triage-logs"
LOG_FILE="$LOG_DIR/run.log"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set. Add it to .env or export it.}"
: "${GITHUB_REPO:?GITHUB_REPO is not set. Example: owner/repo}"

mkdir -p "$LOG_DIR"
> "$LOG_FILE"

echo ""
echo "[1/2] Running Playwright tests..."
echo "---------------------------------------"

set +e
npx playwright test > "$LOG_FILE" 2>&1
TEST_EXIT=$?
set -e

cat "$LOG_FILE"
echo "---------------------------------------"

if [ "$TEST_EXIT" -eq 0 ]; then
  echo "[OK] All tests passed. Nothing to triage."
  exit 0
fi

LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
echo "      Tests failed ($LINE_COUNT lines). Dispatching pipeline-failure event..."

PAYLOAD=$(SCRIPT_DIR_PY="$SCRIPT_DIR" LOG_FILE_PY="$LOG_FILE" \
  python3 -c "
import json, subprocess, os
script_dir = os.environ['SCRIPT_DIR_PY']
log        = open(os.environ['LOG_FILE_PY']).read()
try:
    branch = subprocess.check_output(['git','-C',script_dir,'rev-parse','--abbrev-ref','HEAD'], stderr=subprocess.DEVNULL).decode().strip()
    commit = subprocess.check_output(['git','-C',script_dir,'rev-parse','--short','HEAD'],      stderr=subprocess.DEVNULL).decode().strip()
except Exception:
    branch, commit = 'unknown', 'unknown'
print(json.dumps({'event_type':'pipeline-failure','client_payload':{'job':'local-playwright-e2e','category':'playwright-e2e','branch':branch,'commit':commit,'log':log}}))
")

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/dispatches" \
  -d "$PAYLOAD")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")

if [ "$HTTP_STATUS" -eq 204 ]; then
  echo "      Dispatch sent."
  echo "      Actions: https://github.com/${GITHUB_REPO}/actions"
else
  echo "      ERROR: Dispatch failed (HTTP $HTTP_STATUS). Body: $BODY"
fi

exit "$TEST_EXIT"
