import os
import json
import urllib.request
import urllib.error


def _github_api(method: str, path: str, token: str, body=None):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    url = f"https://api.github.com/repos/{repo}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"GitHub API {method} {path} failed: {e.code} {e.read().decode()}"
        ) from e


def check_duplicate_issue(signature: str, token: str) -> dict:
    """Returns {"duplicate": True, "issue_number": N, "url": "..."} or {"duplicate": False}."""
    issues = _github_api(
        "GET", "/issues?labels=pipeline-triage&state=open&per_page=50", token
    )
    for issue in issues:
        if signature in issue.get("title", ""):
            return {
                "duplicate": True,
                "issue_number": issue["number"],
                "url": issue["html_url"],
            }
    return {"duplicate": False}


def add_issue_comment(issue_number: int, body: str, token: str) -> dict:
    return _github_api("POST", f"/issues/{issue_number}/comments", token, {"body": body})


def create_github_issue(title: str, body: str, labels: list, token: str) -> dict:
    result = _github_api(
        "POST", "/issues", token, {"title": title, "body": body, "labels": labels}
    )
    return {"issue_number": result["number"], "url": result["html_url"]}
