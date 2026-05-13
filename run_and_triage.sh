#!/bin/bash
# Runs Playwright tests locally. On failure, ships logs to GitHub Actions via repository_dispatch.
# Usage: ./run_and_triage.sh

set -euo pipefail

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set. Add it to .env or export it.}"
: "${GITHUB_REPO:?GITHUB_REPO is not set. Example: myorg/myrepo}"

LOG_FILE="test-results/run.log"
mkdir -p test-results

echo "Running Playwright tests..."
npx playwright test 2>&1 | tee "$LOG_FILE"
TEST_EXIT=${PIPESTATUS[0]}

if [ "$TEST_EXIT" -eq 0 ]; then
  echo "All tests passed."
  exit 0
fi

echo "Tests failed. Sending logs to GitHub Actions..."

# Grab last 150 lines and JSON-encode them safely
LOG_SNIPPET=$(tail -150 "$LOG_FILE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/dispatches" \
  -d "{
    \"event_type\": \"local-test-failure\",
    \"client_payload\": {
      \"job\": \"local-playwright-e2e\",
      \"machine\": \"$(hostname)\",
      \"branch\": \"$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\",
      \"commit\": \"$(git rev-parse --short HEAD 2>/dev/null || echo unknown)\",
      \"log\": $LOG_SNIPPET
    }
  }")

if [ "$HTTP_STATUS" -eq 204 ]; then
  echo "Triage triggered successfully on GitHub Actions (HTTP $HTTP_STATUS)."
else
  echo "Warning: GitHub dispatch returned HTTP $HTTP_STATUS. Check your GITHUB_TOKEN and GITHUB_REPO."
fi

exit "$TEST_EXIT"
