#!/bin/bash
# Runs Playwright tests locally. On failure, ships logs to GitHub Actions via repository_dispatch.
# Usage: ./run_and_triage.sh

# Resolve absolute path of the project root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/test-results"
LOG_FILE="$LOG_DIR/run.log"

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set. Add it to .env or export it.}"
: "${GITHUB_REPO:?GITHUB_REPO is not set. Example: owner/repo}"

mkdir -p "$LOG_DIR"
> "$LOG_FILE"   # create/clear the log file upfront

echo ""
echo "[1/4] Running Playwright tests..."
echo "---------------------------------------"

# Run tests — pipe to tee using absolute path, capture exit code via PIPESTATUS
set +e
npx playwright test 2>&1 | tee "$LOG_FILE"
TEST_EXIT=${PIPESTATUS[0]}
set -e

echo "---------------------------------------"

if [ "$TEST_EXIT" -eq 0 ]; then
  echo "[OK] All tests passed. Nothing to triage."
  exit 0
fi

echo "[2/4] Tests failed (exit code: $TEST_EXIT). Capturing logs..."
LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
echo "      Log captured: $LINE_COUNT lines → $LOG_FILE"

echo "[3/4] Encoding log and sending to GitHub Actions..."
LOG_SNIPPET=$(tail -150 "$LOG_FILE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/dispatches" \
  -d "{
    \"event_type\": \"local-test-failure\",
    \"client_payload\": {
      \"job\": \"local-playwright-e2e\",
      \"machine\": \"$(hostname)\",
      \"branch\": \"$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\",
      \"commit\": \"$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)\",
      \"log\": $LOG_SNIPPET
    }
  }")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")

echo "[4/4] curl response: HTTP $HTTP_STATUS"

if [ "$HTTP_STATUS" -eq 204 ]; then
  echo "      Dispatch sent successfully."
  echo "      Watch the triage run at: https://github.com/${GITHUB_REPO}/actions"
else
  echo "      ERROR: Dispatch failed."
  echo "      Body: $BODY"
  echo "      Check: GITHUB_TOKEN has 'repo' scope and GITHUB_REPO=owner/repo is correct."
fi

exit "$TEST_EXIT"
