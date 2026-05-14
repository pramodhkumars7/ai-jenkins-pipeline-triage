# AI Pipeline Triage Agent

Simulates CI/CD pipeline failures (Playwright E2E tests and EKS deployments), uploads failure logs to GitHub Gists, and triggers a GitHub Actions workflow that uses an AI agent to generate a Root Cause Analysis (RCA), auto-create GitHub Issues, and post results to Microsoft Teams.

---

## How it works

```
Local Machine                              GitHub Actions (pipeline-failure event)
─────────────                              ──────────────────────────────────────
./run_and_triage.sh          ─dispatch─►  triage.yml
  Playwright E2E tests                       │
  category: "playwright-e2e"                 ▼
                                           Python triage_agent.py
./simulate_eks_failure.sh    ─dispatch─►    ├─ Fetches log from Gist raw URL
  Synthetic k8s log                         ├─ Calls GitHub Models (gpt-4o)
  category: "eks-deploy"                    ├─ Tool-calling loop:
                                             │    check_duplicate_issue
                                             │    create_github_issue / add_issue_comment
                                             ├─ Prints RCA to Actions log
                                             └─ Sends Adaptive Card to Teams
```

---

## Prerequisites

- Node.js (v18+)
- Python 3.x
- A GitHub account with access to this repository

---

## Step 1 — Create a GitHub Personal Access Token (Classic)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token → Generate new token (classic)**
3. Fill in:
   - **Note:** `pipeline-triage`
   - **Expiration:** 90 days (or as needed)
4. Under **Select scopes**, tick:
   - `repo` — full repository access (needed to trigger GitHub Actions)
   - `gist` — create and delete Gists (needed to upload logs)
5. Click **Generate token**
6. **Copy the token immediately** — GitHub only shows it once

---

## Step 2 — Create your `.env` file

In the project root, copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=pramodhkumars7/ai-jenkins-pipeline-triage
```

> `.env` is gitignored — it will never be committed. Each team member keeps their own `.env` with their own PAT.

---

## Step 3 — Install dependencies

```bash
npm install
```

---

## Step 4 — Install Playwright browsers

```bash
npx playwright install chromium
```

---

## Step 5a — Run the Playwright triage script

```bash
./run_and_triage.sh
```

The script will:

1. Run all Playwright tests
2. Print test output to the terminal
3. On failure — upload the full log to a secret GitHub Gist
4. Trigger the GitHub Actions triage workflow
5. Print the Gist URL and Actions link

---

## Step 5b — Simulate an EKS deploy failure

```bash
./simulate_eks_failure.sh
```

Or pick a specific scenario:

```bash
./simulate_eks_failure.sh CrashLoopBackOff
./simulate_eks_failure.sh OOMKilled
./simulate_eks_failure.sh ImagePullBackOff
./simulate_eks_failure.sh ReadinessProbeFailed
```

This generates a realistic `kubectl` failure log, uploads it to a secret Gist, and dispatches a `pipeline-failure` event with `category: "eks-deploy"`. The Actions workflow runs the same triage agent and creates a labeled GitHub Issue.

---

## GitHub Actions secrets (repo admin sets these once)

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Description |
|---|---|---|
| `TEAMS_WEBHOOK` | Yes | Incoming webhook URL from your Teams channel (via Workflows) |

> `GITHUB_TOKEN` is auto-injected by GitHub Actions — no setup needed.
> `PAT_TOKEN` is no longer required — each developer's log is uploaded via their own local PAT and fetched via a public raw URL.

---

## Getting the Teams webhook URL

1. Open Teams → go to the channel for notifications
2. Click **···** next to the channel name → **Workflows**
3. Search: `Post to a channel when a webhook request is received`
4. Click it → Next → select your team and channel → **Add workflow**
5. Copy the webhook URL and add it as the `TEAMS_WEBHOOK` secret above

---

## Project structure

```
├── src/
│   ├── index.html           # Home page
│   ├── login.html           # Login page
│   └── dashboard.html       # Dashboard page
├── tests/
│   ├── home.spec.js         # Playwright tests (intentionally failing for demo)
│   ├── login.spec.js
│   ├── dashboard.spec.js
│   ├── test_agent_tools.py  # Unit tests for GitHub Issue helpers
│   ├── test_triage_agent.py # Unit tests for tool-calling loop and prompt builder
│   └── test_gen_eks_log.py  # Unit tests for EKS log generator
├── scripts/
│   └── gen_eks_log.py       # Synthetic EKS failure log generator (4 scenarios)
├── prompts/
│   └── agent_prompt.md      # Shared agent prompt template with category branching
├── .github/
│   └── workflows/
│       └── triage.yml       # GitHub Actions workflow
├── triage_agent.py          # AI triage agent with tool-calling (runs in Actions)
├── agent_tools.py           # GitHub Issue create / dedup / comment helpers
├── run_and_triage.sh        # Playwright failure dispatcher
├── simulate_eks_failure.sh  # EKS failure dispatcher
├── requirements.txt         # Pinned Python dependencies
├── playwright.config.js
├── package.json
├── .env.example             # Template for your .env
└── .gitignore
```

---

## Notes

- Each developer uses their own PAT in `.env` — no shared credentials
- GitHub Gists are automatically cleaned up: each run deletes the previous run's Gist before creating a new one
- The triage agent uses `gpt-4o` from GitHub Models — no external API key needed
