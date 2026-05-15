# AI Pipeline Triage Agent

Simulates CI/CD pipeline failures (Playwright E2E tests and EKS deployments), triggers a GitHub Actions workflow that uses GitHub Copilot (Claude Sonnet 4.6) to generate a Root Cause Analysis (RCA), auto-creates a draft fix PR, opens a GitHub Issue, and posts results to Microsoft Teams.

---

## How it works

```
GitHub Actions (simulate.yml)              GitHub Actions (triage.yml / pipeline-failure)
─────────────────────────────              ──────────────────────────────────────────────
simulate-eks job             ─dispatch─►  triage.yml
  (workflow_dispatch / cron)                 │  log embedded in payload
  category: "eks-deploy"                     ▼
                                           triage_agent.py
simulate-playwright job      ─dispatch─►    ├─ gh copilot explain → Claude Sonnet 4.6 RCA
  (workflow_dispatch)                        ├─ detect error class
  category: "playwright-e2e"                 ├─ apply fix to k8s/deployment.yaml or playwright.config.js
                                             ├─ open draft PR with fix
─ OR ─                                       ├─ create / update GitHub Issue
                                             └─ send Adaptive Card to Teams
Local Machine
─────────────
./run_and_triage.sh          ─dispatch─►  (same triage.yml above)
./simulate_eks_failure.sh    ─dispatch─►
```

---

## Prerequisites

- Node.js (v18+)
- Python 3.x
- A GitHub account with access to this repository

---

## Step 1 — Create your `.env` file

In the project root, copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=AI-Ideas-xyz/ai-jenkins-pipeline-triage
```

> `.env` is gitignored — it will never be committed.

---

## Step 2 — Install dependencies

```bash
npm install
```

---

## Step 3 — Install Playwright browsers

```bash
npx playwright install chromium
```

---

## Step 4a — Run the Playwright triage script

```bash
./run_and_triage.sh
```

The script will:

1. Run all Playwright tests
2. Print test output to the terminal
3. On failure — embed the full log in a `pipeline-failure` dispatch to GitHub Actions
4. Print the Actions link

---

## Step 4b — Simulate an EKS deploy failure

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

Generates a realistic `kubectl` failure log and dispatches a `pipeline-failure` event with `category: "eks-deploy"`. The triage workflow runs RCA, patches `k8s/deployment.yaml`, and opens a draft PR.

---

## Step 5 — Trigger the demo from GitHub Actions (no local machine needed)

1. Go to **Actions → Simulate Pipeline Failure → Run workflow**
2. Choose:
   - **Failure category:** `eks-deploy` or `playwright-e2e`
   - **EKS scenario:** `random`, `CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, or `ReadinessProbeFailed` (ignored for Playwright)
3. Click **Run workflow**
4. The simulate job generates a log and dispatches the `pipeline-failure` event
5. The **Pipeline Triage Agent** workflow fires automatically:
   - Claude Sonnet 4.6 analyzes the log and produces an RCA
   - A fix is applied to `k8s/deployment.yaml` (or `playwright.config.js`) and a **draft PR** is opened
   - A GitHub Issue is created (or updated if it's a duplicate)
   - A Teams Adaptive Card is sent (if `TEAMS_WEBHOOK` is configured)

A daily smoke test also runs automatically at **08:00 UTC** (EKS/random scenario).

---

## Getting the Teams webhook URL

1. Open Teams → go to the channel for notifications
2. Click **···** next to the channel name → **Workflows**
3. Search: `Post to a channel when a webhook request is received`
4. Click it → Next → select your team and channel → **Add workflow**
5. Copy the webhook URL and add it as the `TEAMS_WEBHOOK` secret in **Settings → Secrets and variables → Actions**

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
│   ├── test_triage_agent.py # Unit tests for RCA, error detection, and auto-fix
│   └── test_gen_eks_log.py  # Unit tests for EKS log generator
├── scripts/
│   └── gen_eks_log.py       # Synthetic EKS failure log generator (4 scenarios)
├── k8s/
│   └── deployment.yaml      # Sample k8s manifest (auto-patched by triage agent)
├── .github/
│   └── workflows/
│       ├── simulate.yml     # Trigger EKS/Playwright failures from Actions (no local machine)
│       └── triage.yml       # AI triage agent workflow (fires on pipeline-failure event)
├── triage_agent.py          # Triage agent: Copilot RCA, auto-fix PR, Issue, Teams
├── agent_tools.py           # GitHub Issue create / dedup / comment helpers
├── run_and_triage.sh        # Playwright failure dispatcher
├── simulate_eks_failure.sh  # EKS failure dispatcher
├── requirements.txt         # Python dependencies
├── playwright.config.js
├── package.json
├── .env.example             # Template for your .env
└── .gitignore
```

---

## Notes

- No Gist dependency — failure logs are embedded directly in the dispatch payload
- The triage agent uses **GitHub Copilot (Claude Sonnet 4.6)** via `gh copilot explain` — no separate API key needed
- Auto-fix PRs are opened as **drafts** and require human review before merging
