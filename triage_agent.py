"""
Pipeline Triage Agent
  1. Reads dispatch payload (job metadata + gist_raw_url + category)
  2. Fetches full log from the raw Gist URL — no auth needed
  3. Calls GitHub Models (gpt-4o) with tool-calling (check_duplicate_issue,
     add_issue_comment, create_github_issue)
  4. Prints RCA to console
  5. Sends Adaptive Card to Teams
"""
import os
import sys
import json
import urllib.request
import requests
from openai import OpenAI
import agent_tools


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def fetch_log(raw_url: str) -> str:
    with urllib.request.urlopen(raw_url) as resp:
        return resp.read().decode("utf-8")


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_duplicate_issue",
            "description": "Check whether an open GitHub Issue with this failure signature already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "signature": {
                        "type": "string",
                        "description": "Failure signature e.g. '[playwright-e2e] TimeoutError'",
                    }
                },
                "required": ["signature"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_issue_comment",
            "description": "Add a comment to an existing GitHub Issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["issue_number", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_github_issue",
            "description": "Create a new GitHub Issue for this failure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":  {"type": "string"},
                    "body":   {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body", "labels"],
            },
        },
    },
]


def dispatch_tool(name: str, args: dict, token: str) -> str:
    if name == "check_duplicate_issue":
        result = agent_tools.check_duplicate_issue(args["signature"], token)
    elif name == "add_issue_comment":
        result = agent_tools.add_issue_comment(args["issue_number"], args["body"], token)
    elif name == "create_github_issue":
        result = agent_tools.create_github_issue(
            args["title"], args["body"], args["labels"], token
        )
    else:
        result = {"error": f"Unknown tool: {name}"}
    print(f"  Tool '{name}' → {result}")
    return json.dumps(result)


def run_agent_loop(client, messages: list, token: str) -> str:
    while True:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content
        messages.append(msg)
        for tc in msg.tool_calls:
            result = dispatch_tool(
                tc.function.name, json.loads(tc.function.arguments), token
            )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )


# ── Prompt builder ────────────────────────────────────────────────────────────

CATEGORY_INSTRUCTIONS = {
    "playwright-e2e": (
        "Focus on: selector mismatches, assertion errors, timing/flakiness, "
        "broken page structure, baseURL/fixture issues. "
        "When identifying failing tests, include the spec file name and test description. "
        "Suggest exact code changes (e.g. which selector to fix, which timeout to increase)."
    ),
    "eks-deploy": (
        "Focus on: pod status (CrashLoopBackOff / OOMKilled / ImagePullBackOff / ReadinessProbeFailed), "
        "resource limits (memory/CPU), image registry authentication, readiness/liveness probe config. "
        "Suggest concrete `kubectl` commands the on-call engineer can run immediately to verify and fix."
    ),
}

_PROMPT_TEMPLATE = open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "agent_prompt.md")
).read()


def build_prompt(*, job: str, branch: str, commit: str, category: str,
                 gist_raw_url: str, actions_run_url: str) -> str:
    instructions = CATEGORY_INSTRUCTIONS.get(
        category,
        f"Analyze the log for category '{category}' and provide root cause, fix, and confidence.",
    )
    return (
        _PROMPT_TEMPLATE
        .replace("{{job}}", job)
        .replace("{{branch}}", branch)
        .replace("{{commit}}", commit)
        .replace("{{category}}", category)
        .replace("{{gist_raw_url}}", gist_raw_url)
        .replace("{{actions_run_url}}", actions_run_url)
        .replace("{{category_instructions}}", instructions)
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    payload      = json.loads(os.environ["EVENT_PAYLOAD"])
    gh_token     = os.environ["GITHUB_TOKEN"]

    gist_raw_url = payload.get("gist_raw_url", "")
    job          = payload.get("job",      "unknown-job")
    branch       = payload.get("branch",   "unknown")
    commit       = payload.get("commit",   "unknown")
    category     = payload.get("category", "playwright-e2e")

    section("Payload received")
    print(f"  Job      : {job}")
    print(f"  Branch   : {branch}")
    print(f"  Commit   : {commit}")
    print(f"  Category : {category}")

    if not gist_raw_url:
        print("\nERROR: No gist_raw_url in payload — cannot fetch log.")
        sys.exit(1)

    section("Fetching log from Gist")
    log = fetch_log(gist_raw_url)
    line_count = len(log.splitlines())
    print(f"  Log fetched: {line_count} lines")

    section(f"Full failure log ({line_count} lines)")
    print(log)

    section("Running triage agent (GitHub Models + tool-calling)")

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=gh_token,
    )

    actions_run_url = os.environ.get("ACTIONS_RUN_URL", "")
    prompt = build_prompt(
        job=job,
        branch=branch,
        commit=commit,
        category=category,
        gist_raw_url=gist_raw_url,
        actions_run_url=actions_run_url,
    )

    rca = run_agent_loop(client, [{"role": "user", "content": prompt}], gh_token)

    section("RCA & Recommended Fix")
    print(rca)

    section("Sending notification to Teams")
    teams_webhook = os.environ.get("TEAMS_WEBHOOK", "")
    if not teams_webhook:
        print("  TEAMS_WEBHOOK not set — skipping.")
    else:
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
                                "text": f"Pipeline Failure — {job}",
                                "weight": "Bolder",
                                "size": "Medium",
                                "color": "Attention",
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "Job",      "value": job},
                                    {"title": "Branch",   "value": branch},
                                    {"title": "Category", "value": category},
                                ],
                            },
                            {
                                "type": "TextBlock",
                                "text": "RCA & Recommended Fix",
                                "weight": "Bolder",
                                "separator": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": rca + (
                                    f"\n\n[View Actions Run]({actions_run_url})"
                                    if actions_run_url else ""
                                ),
                                "wrap": True,
                            },
                        ],
                    },
                }
            ],
        }
        resp = requests.post(teams_webhook, json=card, timeout=10)
        if resp.status_code in (200, 202):
            print("  Teams notified successfully.")
        else:
            print(f"  Teams notification failed: HTTP {resp.status_code} — {resp.text}")

    section("Triage complete")


if __name__ == "__main__":
    main()
