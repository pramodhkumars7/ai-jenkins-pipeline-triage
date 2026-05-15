#!/bin/bash
# Simulates an EKS pod deployment failure.
# Generates a synthetic kubectl-style failure log and dispatches a pipeline-failure
# event to GitHub Actions with the full log embedded in the payload.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/triage-logs"
LOG_FILE="$LOG_DIR/eks-run.log"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set. Add it to .env or export it.}"
: "${GITHUB_REPO:?GITHUB_REPO is not set. Example: owner/repo}"

mkdir -p "$LOG_DIR"

# ── Pick scenario ──────────────────────────────────────────────────────────────
SCENARIOS=("CrashLoopBackOff" "OOMKilled" "ImagePullBackOff" "ReadinessProbeFailed")
SCENARIO=${1:-${SCENARIOS[$RANDOM % ${#SCENARIOS[@]}]}}

echo ""
echo "[1/2] Generating EKS failure log (scenario: $SCENARIO)..."
echo "---------------------------------------"
python3 "$SCRIPT_DIR/scripts/gen_eks_log.py" "$SCENARIO" > "$LOG_FILE"
cat "$LOG_FILE"
echo "---------------------------------------"
LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
echo "      Log generated ($LINE_COUNT lines)."

echo "[2/2] Dispatching pipeline-failure event to GitHub Actions..."

PAYLOAD=$(SCRIPT_DIR_PY="$SCRIPT_DIR" LOG_FILE_PY="$LOG_FILE" SCENARIO_PY="$SCENARIO" \
  python3 -c "
import json, subprocess, os
script_dir = os.environ['SCRIPT_DIR_PY']
log        = open(os.environ['LOG_FILE_PY']).read()
scenario   = os.environ['SCENARIO_PY']
try:
    branch = subprocess.check_output(['git','-C',script_dir,'rev-parse','--abbrev-ref','HEAD'], stderr=subprocess.DEVNULL).decode().strip()
    commit = subprocess.check_output(['git','-C',script_dir,'rev-parse','--short','HEAD'],      stderr=subprocess.DEVNULL).decode().strip()
except Exception:
    branch, commit = 'unknown', 'unknown'
print(json.dumps({'event_type':'pipeline-failure','client_payload':{'job':'eks-deploy-simulation','category':'eks-deploy','scenario':scenario,'branch':branch,'commit':commit,'log':log}}))
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
  exit 1
fi
