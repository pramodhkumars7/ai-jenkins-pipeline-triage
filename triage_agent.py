"""
Triage agent: fetches full log from GitHub Gist, calls a GitHub-hosted model
(no external API key — uses GITHUB_TOKEN), then notifies Teams.
"""
import os
import json
import urllib.request
import requests
from openai import OpenAI

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)

def fetch_log_from_gist(gist_id: str, token: str) -> str:
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    # Fetch
    req = urllib.request.Request(f"https://api.github.com/gists/{gist_id}", headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    content = list(data["files"].values())[0]["content"]

    # Delete immediately after reading — no Gist accumulation
    del_req = urllib.request.Request(
        f"https://api.github.com/gists/{gist_id}",
        headers=headers,
        method="DELETE"
    )
    urllib.request.urlopen(del_req)
    print(f"Gist {gist_id} deleted after reading.")

    return content

def main():
    payload   = json.loads(os.environ["EVENT_PAYLOAD"])
    pat_token = os.environ["PAT_TOKEN"]   # PAT with gist scope
    gist_id   = payload.get("gist_id", "")
    job      = payload.get("job", "unknown-job")
    machine  = payload.get("machine", "unknown")
    branch   = payload.get("branch", "unknown")
    commit   = payload.get("commit", "unknown")

    if not gist_id:
        print("No gist_id in payload — cannot fetch log.")
        return

    print(f"Fetching full log from Gist {gist_id}...")
    log = fetch_log_from_gist(gist_id, pat_token)
    print(f"Log fetched: {len(log.splitlines())} lines")

    prompt = f"""You are a senior QA/DevOps engineer. A Playwright E2E test suite just failed.

Context:
- Job    : {job}
- Machine: {machine}
- Branch : {branch}
- Commit : {commit}

Analyze the full failure log and provide:
1. **Root Cause** – 2-3 sentences on what failed and why.
2. **Affected Tests** – bullet list of failing test names.
3. **Recommended Fix** – concrete steps a developer can follow.
4. **Confidence** – High / Medium / Low.

Be concise. Use Markdown.

--- FULL FAILURE LOG ---
{log}
"""

    print("Calling GitHub Models for RCA...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    rca = response.choices[0].message.content

    # ── Teams notification ────────────────────────────────────────────────────
    teams_webhook = os.environ.get("TEAMS_WEBHOOK")
    if teams_webhook:
        teams_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary": f"Pipeline Failure — {job}",
            "sections": [{
                "activityTitle": f"Pipeline Failure: `{job}`",
                "activitySubtitle": f"Branch: `{branch}` | Commit: `{commit}` | Machine: `{machine}`",
                "text": rca,
                "markdown": True
            }]
        }
        r = requests.post(teams_webhook, json=teams_payload)
        print(f"Teams notified: HTTP {r.status_code}")
    else:
        print("TEAMS_WEBHOOK not set — skipping Teams notification.")

    print("\n=== RCA ===\n")
    print(rca)


if __name__ == "__main__":
    main()
