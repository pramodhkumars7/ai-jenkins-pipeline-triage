#!/bin/bash
# Runs Playwright tests locally. On failure:
#   1. Uploads full log to a secret GitHub Gist (no size limit)
#   2. Sends Gist ID to GitHub Actions via repository_dispatch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# triage-logs/, NOT test-results/ — Playwright wipes test-results/ on every run
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
echo "[1/4] Running Playwright tests..."
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
echo "[2/4] Tests failed ($LINE_COUNT lines). Uploading full log to GitHub Gist..."

# Verify token has gist scope before attempting upload
TOKEN_SCOPES=$(curl -s -I \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/user | grep -i "x-oauth-scopes" | tr -d '\r')
echo "      Token scopes: ${TOKEN_SCOPES:-none detected}"
if ! echo "$TOKEN_SCOPES" | grep -qi "gist"; then
  echo "      ERROR: GITHUB_TOKEN is missing 'gist' scope."
  echo "      Go to github.com/settings/tokens → edit token → tick 'gist' → regenerate → update .env"
  exit 1
fi

# Upload the entire log file to a secret Gist — no size limit
LOG_CONTENT=$(python3 -c "import sys,json; print(json.dumps(open('$LOG_FILE').read()))")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

GIST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/gists \
  -d "{
    \"description\": \"Pipeline triage log — ${TIMESTAMP}\",
    \"public\": false,
    \"files\": {
      \"playwright-failure.log\": {
        \"content\": $LOG_CONTENT
      }
    }
  }")

GIST_ID=$(echo "$GIST_RESPONSE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('id',''))" 2>/dev/null)
GIST_URL=$(echo "$GIST_RESPONSE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('html_url',''))" 2>/dev/null)

if [ -z "$GIST_ID" ]; then
  echo "      ERROR: Gist upload failed. Response: $GIST_RESPONSE"
  exit "$TEST_EXIT"
fi

echo "      Gist created: $GIST_URL"

echo "[3/4] Sending Gist ID to GitHub Actions..."

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/dispatches" \
  -d "{
    \"event_type\": \"local-test-failure\",
    \"client_payload\": {
      \"job\": \"local-playwright-e2e\",
      \"branch\": \"$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\",
      \"commit\": \"$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)\",
      \"gist_id\": \"$GIST_ID\"
    }
  }")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")

echo "[4/4] curl response: HTTP $HTTP_STATUS"

if [ "$HTTP_STATUS" -eq 204 ]; then
  echo "      Dispatch sent. Full log: $GIST_URL"
  echo "      Actions: https://github.com/${GITHUB_REPO}/actions"
else
  echo "      ERROR: Dispatch failed. Body: $BODY"
fi

exit "$TEST_EXIT"
