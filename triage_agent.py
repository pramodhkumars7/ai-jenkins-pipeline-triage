"""
Pipeline Triage Agent
  1. Reads dispatch payload (job metadata + gist_id)
  2. Fetches full log from GitHub Gist using PAT_TOKEN
  3. Deletes the Gist immediately (no accumulation)
  4. Calls GitHub Models (gpt-4o-mini) via GITHUB_TOKEN — no external API key
  5. Prints RCA to console
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


def fetch_and_delete_gist(gist_id: str, pat_token: str) -> str:
    """Fetches the Gist content then immediately deletes it."""
    headers = {
        "Authorization": f"token {pat_token}",   # value never printed
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/gists/{gist_id}"

    # Fetch
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers)
    ) as resp:
        data = json.loads(resp.read())

    content = list(data["files"].values())[0]["content"]

    # Delete
    urllib.request.urlopen(
        urllib.request.Request(url, headers=headers, method="DELETE")
    )

    return content


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    payload   = json.loads(os.environ["EVENT_PAYLOAD"])
    pat_token = os.environ["PAT_TOKEN"]       # used for Gist, never printed
    gh_token  = os.environ["GITHUB_TOKEN"]    # used for Models, never printed

    gist_id = payload.get("gist_id", "")
    job     = payload.get("job",     "unknown-job")
    machine = payload.get("machine", "unknown")
    branch  = payload.get("branch",  "unknown")
    commit  = payload.get("commit",  "unknown")

    # ── 1. Print metadata (no secrets) ───────────────────────────────────────
    section("Payload received from local machine")
    print(f"  Job     : {job}")
    print(f"  Machine : {machine}")
    print(f"  Branch  : {branch}")
    print(f"  Commit  : {commit}")
    print(f"  Gist ID : {gist_id}")

    if not gist_id:
        print("\nERROR: No gist_id in payload — cannot fetch log.")
        return

    # ── 2. Fetch full log from Gist + delete it ───────────────────────────────
    section("Fetching log from Gist")
    log = fetch_and_delete_gist(gist_id, pat_token)
    line_count = len(log.splitlines())
    print(f"  Log fetched  : {line_count} lines")
    print(f"  Gist deleted : {gist_id}")

    # ── 3. Print the raw log ──────────────────────────────────────────────────
    section(f"Full test failure log ({line_count} lines)")
    print(log)

    # ── 4. Call GitHub Models for RCA ─────────────────────────────────────────
    section("Calling GitHub Models (gpt-4o-mini) for analysis")

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=gh_token,    # not printed
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
        # Adaptive Card — works with Teams Workflows webhook
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
