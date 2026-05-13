"""
Triage agent: reads the test failure payload from GitHub Actions env,
calls a GitHub-hosted model (no external API key — uses GITHUB_TOKEN),
then notifies Teams.
"""
import os
import json
import requests
from openai import OpenAI

# GitHub Models endpoint — uses the auto-injected GITHUB_TOKEN in Actions
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)

def main():
    payload  = json.loads(os.environ["EVENT_PAYLOAD"])
    log      = payload.get("log", "(no log provided)")
    job      = payload.get("job", "unknown-job")
    machine  = payload.get("machine", "unknown")
    branch   = payload.get("branch", "unknown")
    commit   = payload.get("commit", "unknown")

    prompt = f"""You are a senior QA/DevOps engineer. A Playwright E2E test suite just failed.

Context:
- Job    : {job}
- Machine: {machine}
- Branch : {branch}
- Commit : {commit}

Analyze the failure log and provide:
1. **Root Cause** – 2-3 sentences on what failed and why.
2. **Affected Tests** – bullet list of failing test names.
3. **Recommended Fix** – concrete steps a developer can follow.
4. **Confidence** – High / Medium / Low.

Be concise. Use Markdown.

--- FAILURE LOG ---
{log}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",   # free-tier GitHub Model; swap to gpt-4o for deeper analysis
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
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
