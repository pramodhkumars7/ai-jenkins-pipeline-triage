"""
Pipeline Triage Agent
  1. Reads dispatch payload (job metadata + gist_raw_url)
  2. Fetches full log from the raw Gist URL — no auth needed
  3. Calls GitHub Models (gpt-4o-mini) via auto-injected GITHUB_TOKEN
  4. Prints RCA to console
  5. Sends Adaptive Card to Teams
"""
import os
import json
import urllib.request
import requests
from openai import OpenAI


# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def fetch_log(raw_url: str) -> str:
    """Fetches log from Gist raw URL — no authentication required."""
    with urllib.request.urlopen(raw_url) as resp:
        return resp.read().decode("utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    payload      = json.loads(os.environ["EVENT_PAYLOAD"])
    gh_token     = os.environ["GITHUB_TOKEN"]   # for GitHub Models, never printed

    gist_raw_url = payload.get("gist_raw_url", "")
    job          = payload.get("job",     "unknown-job")
    branch       = payload.get("branch",  "unknown")
    commit       = payload.get("commit",  "unknown")

    # ── 1. Print metadata (no secrets) ───────────────────────────────────────
    section("Payload received from local machine")
    print(f"  Job    : {job}")
    print(f"  Branch : {branch}")
    print(f"  Commit : {commit}")

    if not gist_raw_url:
        print("\nERROR: No gist_raw_url in payload — cannot fetch log.")
        return

    # ── 2. Fetch log from raw Gist URL (no auth) ──────────────────────────────
    section("Fetching log from Gist")
    log = fetch_log(gist_raw_url)
    line_count = len(log.splitlines())
    print(f"  Log fetched : {line_count} lines")
    print(f"  Note        : Gist will be auto-deleted on the next local run")

    # ── 3. Print the raw log ──────────────────────────────────────────────────
    section(f"Full test failure log ({line_count} lines)")
    print(log)

    # ── 4. Call GitHub Models for RCA ─────────────────────────────────────────
    section("Calling GitHub Models (gpt-4o-mini) for analysis")

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=gh_token,   # not printed
    )

    prompt = f"""You are a senior QA/DevOps engineer reviewing a Playwright E2E test failure.

Run context:
- Job    : {job}
- Branch : {branch}

Analyze the failure log below and respond with:

## Root Cause
2-3 sentences explaining what failed and why.

## Affected Tests
Bullet list of each failing test name.

## Recommended Fix
Numbered, concrete steps a developer can follow immediately.

## Confidence
High / Medium / Low — and one sentence why.

--- FULL FAILURE LOG ---
{log}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    rca = response.choices[0].message.content

    # ── 5. Print RCA to console ───────────────────────────────────────────────
    section("RCA & Recommended Fix")
    print(rca)

    # ── 6. Notify Teams ───────────────────────────────────────────────────────
    section("Sending notification to Teams")
    teams_webhook = os.environ.get("TEAMS_WEBHOOK", "")
    actions_url   = os.environ.get("ACTIONS_RUN_URL", "")

    if not teams_webhook:
        print("  TEAMS_WEBHOOK not set — skipping Teams notification.")
    else:
        view_action = f"\n\n[View Actions Run]({actions_url})" if actions_url else ""
        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": f"🔴 Pipeline Failure — {job}",
                                "weight": "Bolder",
                                "size": "Medium",
                                "color": "Attention"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "Job",    "value": job},
                                    {"title": "Branch", "value": branch}
                                ]
                            },
                            {
                                "type": "TextBlock",
                                "text": "RCA & Recommended Fix",
                                "weight": "Bolder",
                                "separator": True
                            },
                            {
                                "type": "TextBlock",
                                "text": rca + view_action,
                                "wrap": True
                            }
                        ]
                    }
                }
            ]
        }

        resp = requests.post(teams_webhook, json=card, timeout=10)
        if resp.status_code in (200, 202):
            print("  Teams notified successfully.")
        else:
            print(f"  Teams notification failed: HTTP {resp.status_code} — {resp.text}")

    section("Triage complete")


if __name__ == "__main__":
    main()
