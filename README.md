# AI Pipeline Triage Agent

Runs Playwright E2E tests locally. On failure, uploads the full log to a GitHub Gist and triggers a GitHub Actions workflow that uses a GitHub-hosted AI model to generate a Root Cause Analysis (RCA), then posts it to a Microsoft Teams channel.

---

## How it works

```
Local Machine
  └── ./run_and_triage.sh
        ├── runs Playwright tests
        ├── on failure → uploads log to secret GitHub Gist (your PAT)
        └── triggers GitHub Actions via repository_dispatch

GitHub Actions
  └── triage_agent.py
        ├── fetches full log from Gist raw URL (no auth needed)
        ├── calls GitHub Models (gpt-4o-mini) for RCA
        ├── prints RCA to Actions console
        └── sends Adaptive Card to Teams channel
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

## Step 5 — Run the triage script

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
│   ├── index.html          # Home page
│   ├── login.html          # Login page
│   └── dashboard.html      # Dashboard page
├── tests/
│   ├── home.spec.js        # Playwright tests (intentionally failing for demo)
│   ├── login.spec.js
│   └── dashboard.spec.js
├── .github/
│   └── workflows/
│       └── triage.yml      # GitHub Actions workflow
├── triage_agent.py         # AI triage agent (runs in Actions)
├── run_and_triage.sh       # Local runner script
├── playwright.config.js
├── package.json
├── .env.example            # Template for your .env
└── .gitignore
```

---

## Notes

- Each developer uses their own PAT in `.env` — no shared credentials
- GitHub Gists are automatically cleaned up: each run deletes the previous run's Gist before creating a new one
- The triage agent uses `gpt-4o-mini` from GitHub Models — no external API key needed
