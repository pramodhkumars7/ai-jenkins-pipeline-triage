"""
Pipeline Triage Agent
  1. Reads dispatch payload (job metadata + log + category)
  2. Gets RCA from gh copilot explain (Claude Sonnet 4.6)
  3. Applies fix to k8s/playwright files and opens a draft PR
  4. Creates/updates GitHub Issue (dedup by signature)
  5. Sends Adaptive Card to Teams
"""
import os
import sys
import json
import subprocess
import pathlib
import requests
import re
import agent_tools


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


CATEGORY_INSTRUCTIONS = {
    "playwright-e2e": (
        "Focus on: selector mismatches, assertion errors, timing/flakiness, "
        "broken page structure, baseURL/fixture issues. "
        "Identify the failing spec file and test description. "
        "Suggest the exact selector or timeout fix."
    ),
    "eks-deploy": (
        "Focus on: pod status (CrashLoopBackOff/OOMKilled/ImagePullBackOff/ReadinessProbeFailed), "
        "resource limits, image registry authentication, readiness/liveness probe config. "
        "Suggest concrete kubectl commands to verify and fix immediately."
    ),
}


# ── RCA via GitHub Copilot (Claude Sonnet 4.6) ────────────────────────────────

def get_rca(log: str, category: str) -> str:
    instructions = CATEGORY_INSTRUCTIONS.get(
        category,
        f"Analyze this '{category}' failure and identify root cause and fix.",
    )
    prompt = (
        f"You are a CI/CD triage expert. {instructions}\n\n"
        f"Analyze the following failure log and provide:\n"
        f"1. Root cause (what went wrong and why)\n"
        f"2. Recommended fix with specific steps\n"
        f"3. Confidence level (High/Medium/Low)\n\n"
        f"Failure log:\n{log}"
    )
    result = subprocess.run(
        ["gh", "copilot", "-p", prompt, "--silent", "--no-ask-user", "--model", "claude-sonnet-4.6"],
        capture_output=True, text=True, timeout=120,
        env={
            **os.environ,
            "GH_PROMPT_DISABLED": "1",
            "GH_TOKEN": os.environ.get("COPILOT_PAT", ""),
            "GITHUB_TOKEN": "",
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh copilot explain failed:\n{result.stderr}")
    return result.stdout.strip()


def detect_error_class(log: str, rca: str) -> str:
    combined = (log + " " + rca).lower()
    for cls in ["OOMKilled", "CrashLoopBackOff", "ImagePullBackOff",
                "ReadinessProbeFailed", "TimeoutError", "AssertionError"]:
        if cls.lower() in combined:
            return cls
    return "Unknown"


# ── EKS auto-fix ──────────────────────────────────────────────────────────────

_EKS_FIXES = {
    "OOMKilled": {
        "replacements": [('memory: "256Mi"', 'memory: "512Mi"')],
        "branch": "fix/eks-oomkilled-increase-memory",
        "msg": "fix: increase memory limit to 512Mi to prevent OOMKilled",
    },
    "ImagePullBackOff": {
        "replacements": [("image: myapp:v2.3.1", "image: myapp:v2.3.2")],
        "branch": "fix/eks-imagepull-update-tag",
        "msg": "fix: update image tag to resolve ImagePullBackOff",
    },
    "ReadinessProbeFailed": {
        "replacements": [
            ("failureThreshold: 3", "failureThreshold: 6"),
            ("initialDelaySeconds: 10", "initialDelaySeconds: 30"),
        ],
        "branch": "fix/eks-readiness-probe-thresholds",
        "msg": "fix: increase readiness probe thresholds to resolve ReadinessProbeFailed",
    },
    "CrashLoopBackOff": {
        "replacements": [(
            "env: []",
            "env:\n        - name: DATABASE_URL\n          value: postgresql://db-service:5432/appdb",
        )],
        "branch": "fix/eks-crashloop-db-env",
        "msg": "fix: add DATABASE_URL env var to resolve startup failure",
    },
}


def apply_eks_fix(error_class: str) -> tuple:
    fix = _EKS_FIXES.get(error_class)
    if not fix:
        return None, None, []
    manifest = pathlib.Path("k8s/deployment.yaml")
    content = manifest.read_text()
    for old, new in fix["replacements"]:
        content = content.replace(old, new)
    manifest.write_text(content)
    return fix["branch"], fix["msg"], ["k8s/deployment.yaml"]


# ── Playwright auto-fix ───────────────────────────────────────────────────────

def apply_playwright_fix() -> tuple:
    config = pathlib.Path("playwright.config.js")
    content = config.read_text()
    new_content = content.replace("timeout: 30000", "timeout: 60000")
    if new_content == content:
        return None, None, []
    config.write_text(new_content)
    return (
        "fix/playwright-increase-timeout",
        "fix: increase Playwright default timeout to 60s",
        ["playwright.config.js"],
    )


# ── Draft PR ──────────────────────────────────────────────────────────────────

def parse_rca(rca_text):
    """Parse RCA text into structured sections"""
    sections = {'cause': '', 'fix': '', 'confidence': 'Medium', 'steps': []}
    lines = rca_text.split('\n')
    current_section = None

    for line in lines:
        line_lower = line.lower().strip()
        if 'root cause' in line_lower or 'what went wrong' in line_lower:
            current_section = 'cause'
            continue
        elif 'recommended fix' in line_lower or 'solution' in line_lower or 'how to fix' in line_lower:
            current_section = 'fix'
            continue
        elif 'confidence' in line_lower:
            for level in ['high', 'medium', 'low']:
                if level in line_lower:
                    sections['confidence'] = level.capitalize()
            continue
        if re.match(r'^\d+\.', line.strip()):
            sections['steps'].append(line.strip())
            continue
        if current_section and line.strip():
            if sections[current_section]:
                sections[current_section] += '\n' + line
            else:
                sections[current_section] = line

    for key in ['cause', 'fix']:
        sections[key] = sections[key].strip()
    return sections


def truncate_smart(text, max_length=400):
    """Intelligently truncate text while preserving meaning"""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    cut_point = max(last_period, last_newline)
    if cut_point > max_length * 0.7:
        return truncated[:cut_point + 1] + " [...]"
    return truncated + "..."


def get_severity_color(error_class):
    """Map error type to color for visual emphasis"""
    critical_errors = ['OOMKilled', 'CrashLoopBackOff', 'AssertionError']
    warning_errors = ['TimeoutError', 'ReadinessProbeFailed']
    if error_class in critical_errors:
        return 'Attention'
    elif error_class in warning_errors:
        return 'Warning'
    return 'Default'


def get_priority_emoji(confidence):
    """Visual indicator for confidence/priority"""
    if confidence == 'High':
        return '🔴'
    elif confidence == 'Medium':
        return '🟡'
    return '🟢'


def create_draft_pr(branch: str, commit_msg: str, files: list,
                    rca: str, error_class: str, token: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    gh_env = {**os.environ, "GITHUB_TOKEN": token}
    # If branch already exists remotely, skip commit/push
    remote_check = subprocess.run(
        ["git", "ls-remote", "--heads", remote_url, branch],
        capture_output=True, text=True,
    )
    branch_exists = bool(remote_check.stdout.strip())
    if not branch_exists:
        subprocess.run(["git", "config", "user.email", "triage-agent@github-actions"], check=True)
        subprocess.run(["git", "config", "user.name", "Pipeline Triage Agent"], check=True)
        saved = {f: pathlib.Path(f).read_text() for f in files}
        subprocess.run(["git", "checkout", "-b", branch], check=True)
        for path, content in saved.items():
            pathlib.Path(path).write_text(content)
        subprocess.run(["git", "add"] + files, check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push", remote_url, branch], check=True)
    # Return existing open PR URL if one exists, otherwise create it
    existing = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "url,state", "-q", "select(.state==\"OPEN\") | .url"],
        capture_output=True, text=True, env=gh_env,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        print(f"  Returning existing open PR for branch {branch}")
        return existing.stdout.strip()
    pr_body = (
        f"## Auto-fix: {error_class}\n\n"
        f"### Root Cause Analysis\n{rca}\n\n"
        f"### Files changed\n"
        + "\n".join(f"- `{f}`" for f in files)
        + "\n\n> Auto-generated by Pipeline Triage Agent — review before merging."
    )
    result = subprocess.run(
        ["gh", "pr", "create",
         "--title", f"[auto-fix] {commit_msg}",
         "--body", pr_body,
         "--draft",
         "--base", "main",
         "--head", branch],
        capture_output=True, text=True, env=gh_env,
    )
    if result.returncode != 0:
        print(f"  PR creation failed: {result.stderr}")
        return ""
    return result.stdout.strip()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    payload   = json.loads(os.environ["EVENT_PAYLOAD"])
    gh_token  = os.environ["GITHUB_TOKEN"]

    log_raw  = payload.get("log", "")
    log      = json.dumps(log_raw, indent=2) if isinstance(log_raw, dict) else str(log_raw)
    job      = payload.get("job",      "unknown-job")
    branch   = payload.get("branch",   "unknown")
    commit   = payload.get("commit",   "unknown")
    category = payload.get("category", "eks-deploy")

    section("Payload received")
    print(f"  Job      : {job}")
    print(f"  Branch   : {branch}")
    print(f"  Commit   : {commit}")
    print(f"  Category : {category}")
    print(f"  Log size : {len(log)} chars")

    if not log.strip():
        print("\nERROR: No log in payload.")
        sys.exit(1)

    section("Getting RCA from GitHub Copilot (Claude Sonnet 4.6)")
    rca = get_rca(log, category)
    print(rca)

    error_class = detect_error_class(log, rca)
    print(f"\n  Detected error class: {error_class}")

    section("Applying auto-fix and creating draft PR")
    actions_run_url = os.environ.get("ACTIONS_RUN_URL", "")
    pr_url = ""
    try:
        if category == "eks-deploy":
            fix_branch, commit_msg, files = apply_eks_fix(error_class)
        else:
            fix_branch, commit_msg, files = apply_playwright_fix()

        if fix_branch:
            pr_url = create_draft_pr(fix_branch, commit_msg, files, rca, error_class, gh_token)
            print(f"  Draft PR: {pr_url}")
        else:
            print(f"  No auto-fix available for: {error_class}")
    except Exception as e:
        print(f"  Auto-fix failed (non-fatal): {e}")

    section("Creating/updating GitHub Issue")
    signature    = f"[{category}] {error_class}"
    comment_body = (
        f"**RCA**\n{rca}"
        + (f"\n\n**Auto-fix PR:** {pr_url}" if pr_url else "")
        + (f"\n\n**Actions run:** {actions_run_url}" if actions_run_url else "")
    )
    dup = agent_tools.check_duplicate_issue(signature, gh_token)
    if dup["duplicate"]:
        agent_tools.add_issue_comment(dup["issue_number"], comment_body, gh_token)
        print(f"  Commented on existing issue #{dup['issue_number']}: {dup['url']}")
    else:
        issue_body = (
            f"## Root Cause Analysis\n{rca}\n\n"
            + (f"## Auto-fix PR\n{pr_url}\n\n" if pr_url else "")
            + f"**Log excerpt:**\n```\n{log[:3000]}\n```"
        )
        result = agent_tools.create_github_issue(
            signature, issue_body, ["pipeline-triage", category], gh_token
        )
        print(f"  Issue created: {result['url']}")

    section("Sending notification to Teams")
    teams_webhook = os.environ.get("TEAMS_WEBHOOK", "")
    if not teams_webhook:
        print("  TEAMS_WEBHOOK not set — skipping.")
    else:
        # Parse RCA into structured sections
        sections = parse_rca(rca)
        severity_color = get_severity_color(error_class)
        priority_emoji = get_priority_emoji(sections['confidence'])

        # Create enhanced readable card
        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.5",
                    "body": [
                        # Header
                        {
                            "type": "Container",
                            "style": "emphasis",
                            "items": [{
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "Image",
                                            "url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
                                            "size": "Small",
                                            "width": "32px"
                                        }]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "❌ Pipeline Failure Detected",
                                                "weight": "Bolder",
                                                "size": "Large",
                                                "color": severity_color,
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"{job}",
                                                "size": "Small",
                                                "spacing": "None",
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": priority_emoji,
                                            "size": "ExtraLarge",
                                            "horizontalAlignment": "Right",
                                        }]
                                    }
                                ]
                            }]
                        },
                        # Quick facts
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "items": [{
                                "type": "FactSet",
                                "facts": [
                                    {"title": "🌿 Branch", "value": branch[:50]},
                                    {"title": "📦 Category", "value": category},
                                    {"title": "⚠️ Error Type", "value": error_class},
                                    {"title": "🎯 Confidence", "value": f"{sections['confidence']} {priority_emoji}"},
                                ]
                            }]
                        },
                        # Root cause
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "style": "accent",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "🔍 Root Cause",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": truncate_smart(sections['cause'], 350) if sections['cause'] else "Analyzing...",
                                    "wrap": True,
                                    "spacing": "Small",
                                }
                            ]
                        },
                        # Recommended fix
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "💡 Recommended Fix",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": truncate_smart(sections['fix'], 350) if sections['fix'] else "See PR for details",
                                    "wrap": True,
                                    "spacing": "Small",
                                }
                            ]
                        },
                        # Action steps (if available)
                        *([{
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "📋 Action Steps",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                },
                                *[{
                                    "type": "TextBlock",
                                    "text": step,
                                    "wrap": True,
                                    "spacing": "Small",
                                } for step in sections['steps'][:3]]
                            ]
                        }] if sections['steps'] else []),
                        # Status footer
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "items": [{
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": f"{'✅ Auto-fix PR created' if pr_url else '⚠️ Manual fix required'}",
                                            "size": "Small",
                                            "weight": "Bolder",
                                            "color": "Good" if pr_url else "Warning",
                                        }]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": "🤖 AI Triage Agent",
                                            "size": "Small",
                                            "color": "Accent",
                                            "horizontalAlignment": "Right",
                                        }]
                                    }
                                ]
                            }]
                        }
                    ],
                    "actions": [a for a in [
                        {"type": "Action.OpenUrl", "title": "📝 View PR", "url": pr_url, "style": "positive"} if pr_url else None,
                        {"type": "Action.OpenUrl", "title": "🔗 Full Analysis", "url": actions_run_url} if actions_run_url else None,
                    ] if a is not None]
                },
            }],
        }
        resp = requests.post(teams_webhook, json=card, timeout=10)
        if resp.status_code in (200, 202):
            print("  Teams notified successfully.")
        else:
            print(f"  Teams notification failed: HTTP {resp.status_code} — {resp.text}")

    section("Triage complete")


if __name__ == "__main__":
    main()
