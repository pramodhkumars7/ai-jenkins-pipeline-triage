# Jenkins CI/CD Pipeline for AI-Powered Triage

Complete guide for setting up a local Jenkins environment with Docker that runs E2E tests and Kubernetes deployment simulations, then triggers AI-powered triage workflows using Claude.

---

## 📋 Table of Contents

- [Quick Start](#-quick-start-5-minutes)
- [Prerequisites](#-prerequisites)
- [Docker Installation](#-docker-installation)
- [Jenkins Setup](#-jenkins-setup)
- [Plugin Installation](#-plugin-installation)
- [Pipeline Configuration](#-pipeline-configuration)
- [Running Tests](#-running-tests)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Architecture](#-architecture)

---

## ⚡ Quick Start (5 Minutes)

```bash
# 1. Clone repository
git clone https://github.com/pramodhkumars7/ai-jenkins-pipeline-triage.git
cd ai-jenkins-pipeline-triage

# 2. Create .env file
cp .env.example .env
# Edit .env and add your GitHub token

# 3. Start Jenkins
cd jenkins
./setup.sh

# 4. Access Jenkins
# Open http://localhost:8080
# Login: admin / admin123

# 5. Configure (see detailed steps below)
# - Add GitHub token to Jenkins credentials
# - Create pipeline job
# - Run first build
```

---

## 🔧 Prerequisites

### Required Software

| Software | Minimum Version | Check Command |
|----------|----------------|---------------|
| **Docker Desktop** | 20.10+ | `docker --version` |
| **Git** | 2.0+ | `git --version` |
| **bash/zsh** | Any | Built-in on Mac/Linux |

### System Requirements

- **CPU:** 2+ cores
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 10GB free space
- **OS:** macOS, Linux, Windows with WSL2

### GitHub Requirements

- GitHub account with access to target repository
- Personal Access Token with permissions:
  - `repo` (Full control of private repositories)
  - `workflow` (Update GitHub Action workflows)
  - Optional: `read:org` (Read org and team membership)

---

## 🐳 Docker Installation

### macOS

1. **Download Docker Desktop:**
   - Visit: https://www.docker.com/products/docker-desktop
   - Download for macOS (Intel or Apple Silicon)

2. **Install:**
   ```bash
   # Open the downloaded .dmg file
   # Drag Docker to Applications folder
   ```

3. **Start Docker Desktop:**
   - Open Docker from Applications
   - Wait for Docker to start (icon in menu bar)

4. **Verify Installation:**
   ```bash
   docker --version
   # Should show: Docker version 20.10.x or higher
   
   docker ps
   # Should show empty list (no containers running)
   ```

5. **Configure Resources:**
   - Docker Desktop → Settings → Resources
   - Set:
     - **CPUs:** 2 minimum, 4 recommended
     - **Memory:** 4GB minimum, 8GB recommended
     - **Disk:** 20GB minimum
   - Click "Apply & Restart"

### Linux (Ubuntu/Debian)

```bash
# Update package index
sudo apt-get update

# Install dependencies
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker ps
```

### Windows (WSL2)

1. **Enable WSL2:**
   ```powershell
   # Run in PowerShell as Administrator
   wsl --install
   wsl --set-default-version 2
   ```

2. **Install Docker Desktop:**
   - Download from: https://www.docker.com/products/docker-desktop
   - Run installer
   - Enable "Use WSL 2 based engine" during setup

3. **Verify:**
   ```bash
   # In WSL2 terminal
   docker --version
   docker ps
   ```

---

## 🚀 Jenkins Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/pramodhkumars7/ai-jenkins-pipeline-triage.git
cd ai-jenkins-pipeline-triage
```

### Step 2: Create Environment File

```bash
# Copy example file
cp .env.example .env

# Edit .env file
nano .env  # or use your preferred editor
```

Add your GitHub token:
```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=pramodhkumars7/ai-jenkins-pipeline-triage
```

**How to create GitHub token:**

1. Go to: https://github.com/settings/tokens/new
2. Token name: `Jenkins CI Local`
3. Expiration: `30 days` (or as per your org policy)
4. Scopes:
   - ✅ `repo` (Full control)
   - ✅ `workflow` (Update workflows)
5. Click "Generate token"
6. Copy token immediately (shown only once!)

### Step 3: Build and Start Jenkins

The repository includes a custom Dockerfile that bundles:
- Jenkins LTS
- Node.js 20.x
- Playwright with Chromium
- Python 3
- Git and GitHub CLI

```bash
cd jenkins

# Option A: Automated setup (recommended)
chmod +x setup.sh
./setup.sh

# Option B: Manual setup
docker-compose up -d --build
```

**What the setup does:**

1. Builds custom Jenkins Docker image
2. Creates persistent volume for Jenkins data
3. Mounts your project directory at `/workspace`
4. Exposes Jenkins on port 8080
5. Configures admin user (admin/admin123)
6. Installs required Jenkins plugins

**Wait for Jenkins to start:**

```bash
# Watch logs
docker-compose logs -f jenkins

# Wait for this message:
# "Jenkins is fully up and running"
```

### Step 4: Access Jenkins

1. Open browser: http://localhost:8080
2. Login credentials:
   - **Username:** `admin`
   - **Password:** `admin123`

⚠️ **Security Note:** These are default credentials for local development only. Change them in production!

### Step 5: Verify Installation

```bash
# Check container is running
docker ps | grep jenkins-local

# Check mounted directory
docker exec jenkins-local ls -la /workspace

# Check Node.js is available
docker exec jenkins-local node --version

# Check Playwright is available
docker exec jenkins-local npx playwright --version
```

---

## 🔌 Plugin Installation

The Jenkins container comes pre-installed with required plugins via the Dockerfile. However, if you need to install plugins manually:

### Pre-installed Plugins

These plugins are automatically installed:

- **git** - Git integration
- **workflow-aggregator** - Pipeline plugin suite
- **git-parameter** - Git branch parameter (for branch selection)
- **credentials-binding** - Credential management
- **docker-workflow** - Docker pipeline integration

### Verify Plugins

1. Go to: **Manage Jenkins** → **Manage Plugins**
2. Click **Installed** tab
3. Search for:
   - Git Plugin
   - Pipeline
   - Git Parameter

### Manual Plugin Installation (if needed)

If a plugin is missing:

1. **Via UI:**
   - Manage Jenkins → Manage Plugins
   - Click **Available** tab
   - Search for plugin name
   - Check the box
   - Click **Install without restart**

2. **Via Dockerfile (persistent):**
   ```dockerfile
   # Edit jenkins/Dockerfile
   RUN jenkins-plugin-cli --plugins \
       git \
       workflow-aggregator \
       git-parameter \
       your-new-plugin
   ```
   
   Then rebuild:
   ```bash
   cd jenkins
   docker-compose down
   docker-compose up -d --build
   ```

### Critical: Git Parameter Plugin

The **Git Parameter Plugin** is essential for branch selection in the UI.

**To verify it's working:**

1. Create a pipeline (see next section)
2. Run build once
3. "Build with Parameters" should show a dropdown with branches

**If branches don't appear:**

```bash
# Check plugin is installed
docker exec jenkins-local jenkins-plugin-cli --list | grep git-parameter

# If missing, install manually:
docker exec jenkins-local jenkins-plugin-cli --plugins git-parameter

# Restart Jenkins
docker restart jenkins-local
```

---

## ⚙️ Pipeline Configuration

### Part 1: Add GitHub Token to Jenkins

This allows Jenkins to call GitHub API to trigger Actions workflows.

1. **Navigate to Credentials:**
   - Manage Jenkins → Credentials
   - Click **(global)** domain
   - Click **Add Credentials**

2. **Fill Credential Form:**

   | Field | Value |
   |-------|-------|
   | **Kind** | Secret text |
   | **Scope** | Global |
   | **Secret** | `ghp_xxxx...` (paste your GitHub token) |
   | **ID** | `github-pat-token` ⚠️ EXACTLY THIS! |
   | **Description** | GitHub PAT for API |

3. **Save:**
   - Click **Create**
   - Verify credential appears in list

⚠️ **Critical:** The ID must be exactly `github-pat-token` (case-sensitive). This matches the reference in Jenkinsfile line 32.

### Part 2: Create Pipeline Job

1. **Create New Item:**
   - Jenkins Dashboard → **New Item**
   - Name: `E2E-Triage-Pipeline`
   - Type: **Pipeline**
   - Click **OK**

2. **Configure Pipeline:**

   Scroll to **Pipeline** section:

   - **Definition:** `Pipeline script from SCM`
   - **SCM:** `Git`
   - **Repository URL:** `file:///workspace`
     - This is the path INSIDE the container
     - Your project is mounted at `/workspace`
     - Don't change this!
   - **Credentials:** `- none -` (local file system)
   - **Branches to build:** `*/main` (or your branch)
   - **Script Path:** `jenkins/Jenkinsfile`

3. **Optional Settings:**

   - **Description:** Add a description
   - **Discard old builds:** Check and set max 10 builds

4. **Save:**
   - Click **Save** at bottom
   - You'll be taken to pipeline job page

### Part 3: Initialize Parameters

The pipeline has parameters (GIT_BRANCH, TEST_CATEGORY, EKS_SCENARIO) defined in Jenkinsfile. Jenkins discovers them after the first build.

1. **First Build:**
   - Click **Build Now**
   - Build #1 will start
   - It may fail or use defaults - this is expected

2. **After First Build:**
   - Refresh page
   - **"Build with Parameters"** option appears
   - Branch dropdown will be populated

3. **If branches don't show:**
   ```bash
   # Ensure git can see branches in container
   docker exec jenkins-local bash -c "cd /workspace && git branch -r"
   
   # Should show:
   # origin/main
   # origin/poc/setup-jenkins
   # etc.
   ```

---

## 🧪 Running Tests

### Build with Parameters

1. Click **Build with Parameters**
2. Configure parameters:

   **GIT_BRANCH:**
   - Dropdown showing all available branches
   - Select branch to test

   **TEST_CATEGORY:**
   - `playwright-e2e` - Run Playwright E2E tests
   - `eks-deploy` - Simulate Kubernetes failure

   **EKS_SCENARIO** (only for eks-deploy):
   - `CrashLoopBackOff` - Pod crashes repeatedly
   - `OOMKilled` - Out of memory
   - `ImagePullBackOff` - Image pull fails
   - `ReadinessProbeFailed` - Health check fails
   - `random` - Random scenario

3. Click **Build**

### Test Scenarios

#### Scenario 1: Playwright E2E Tests

```
GIT_BRANCH: origin/main
TEST_CATEGORY: playwright-e2e
```

**What happens:**
1. Checks out selected branch
2. Runs `npm install` (installs dependencies)
3. Runs `npm test` (Playwright tests)
4. If tests fail:
   - Captures test output
   - Sanitizes logs (removes sensitive data)
   - Calls GitHub API with `repository_dispatch` event
   - GitHub Actions "Pipeline Triage Agent" workflow triggers
   - Claude analyzes failure and creates:
     - Root Cause Analysis
     - Fix PR with code changes
     - GitHub Issue
     - Teams notification (if configured)

#### Scenario 2: Kubernetes CrashLoopBackOff

```
GIT_BRANCH: origin/main
TEST_CATEGORY: eks-deploy
EKS_SCENARIO: CrashLoopBackOff
```

**What happens:**
1. Runs `python3 scripts/gen_eks_log.py CrashLoopBackOff`
2. Generates synthetic Kubernetes failure log
3. Triggers GitHub Actions with EKS log
4. Claude analyzes and suggests fixes to `k8s/deployment.yaml`

#### Scenario 3: Out of Memory

```
TEST_CATEGORY: eks-deploy
EKS_SCENARIO: OOMKilled
```

Claude suggests increasing memory limits in deployment.

#### Scenario 4: Image Pull Failure

```
TEST_CATEGORY: eks-deploy
EKS_SCENARIO: ImagePullBackOff
```

Claude suggests fixing image name or registry credentials.

### Monitor Build

1. **Console Output:**
   - Click build number (e.g., #2)
   - Click **Console Output**
   - Watch real-time logs

2. **Expected Output:**
   ```
   📋 Checking out branch...
   ✓ Branch checked out successfully
   🚀 Running playwright-e2e tests...
   📦 Installing dependencies...
   ✓ Dependencies installed
   🧪 Running Playwright tests...
   [test output...]
   ❌ Tests failed - Triggering triage workflow...
   ✓ Triage workflow triggered successfully
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ❌ Pipeline failed - Triage workflow triggered
   ```

3. **Verify GitHub Actions:**
   - Go to: https://github.com/your-org/your-repo/actions
   - See "Pipeline Triage Agent" workflow running
   - Click to view:
     - Claude's analysis
     - Generated PR link
     - Issue link

---

## 🔒 Security

### Credentials Protection

**✅ What's Protected:**

1. **GitHub Token:**
   - Stored in Jenkins credentials (encrypted)
   - Automatically masked in console output
   - Never printed in logs
   - Uses `set +x` to prevent command echoing

2. **Log Sanitization:**
   
   All logs are sanitized before sending to GitHub Actions:
   
   ```groovy
   // Jenkinsfile automatically masks:
   - Passwords, secrets, tokens → ***
   - Email addresses → ***@***.***
   - AWS keys → AKIA***
   - Private keys → ***PRIVATE_KEY***
   - Bearer tokens → Bearer ***
   - URLs with credentials → https://***:***@
   ```

3. **Minimal Information Disclosure:**
   - Branch names not exposed
   - Repository URLs masked
   - Generic job names used
   - File paths normalized

### Security Best Practices

**DO:**
- ✅ Use Jenkins credentials for secrets
- ✅ Rotate tokens every 30 days (or per org policy)
- ✅ Use fine-grained tokens with minimal permissions
- ✅ Review console logs for leaks
- ✅ Keep `.env` file in `.gitignore`

**DON'T:**
- ❌ Print credentials with `echo`
- ❌ Run `env` command (exposes all variables)
- ❌ Commit `.env` file to git
- ❌ Use `--no-verify` to skip git hooks
- ❌ Hardcode secrets in Jenkinsfile

### Credential Rotation

When token expires:

1. Generate new token on GitHub
2. Update in Jenkins:
   - Manage Jenkins → Credentials
   - Click `github-pat-token`
   - Click **Update**
   - Paste new token
   - Save
3. Test with new build

---

## 🐛 Troubleshooting

### Issue: Jenkins Won't Start

**Symptoms:**
```bash
docker ps | grep jenkins
# No output
```

**Solutions:**

1. **Check Docker is running:**
   ```bash
   docker info
   ```

2. **Check logs:**
   ```bash
   cd jenkins
   docker-compose logs jenkins
   ```

3. **Port 8080 already in use:**
   ```bash
   # Find what's using port 8080
   lsof -i :8080
   
   # Kill process or change port in docker-compose.yml:
   ports:
     - "8081:8080"  # Use 8081 instead
   ```

4. **Insufficient resources:**
   - Docker Desktop → Settings → Resources
   - Increase CPU to 2+
   - Increase Memory to 4GB+

5. **Clean start:**
   ```bash
   cd jenkins
   docker-compose down -v
   docker-compose up -d --build
   ```

### Issue: Can't Pull Jenkins Image (TLS timeout)

**Symptoms:**
```
failed to solve: jenkins/jenkins:lts: net/http: TLS handshake timeout
```

**Solutions:**

1. **Pull image manually first:**
   ```bash
   docker pull jenkins/jenkins:lts
   docker-compose build
   docker-compose up -d
   ```

2. **Use Google DNS:**
   - Docker Desktop → Settings → Resources → Network
   - Set DNS to: `8.8.8.8, 8.8.4.4`

3. **Disable VPN temporarily:**
   ```bash
   # Test connectivity
   curl -I https://registry-1.docker.io/v2/
   # Should return HTTP 401 (this is good!)
   ```

### Issue: GitHub Actions Not Triggered

**Symptoms:**
- Build succeeds/fails but no GitHub Actions run
- Console shows: `⚠ Trigger failed (HTTP: 403)`

**Solutions:**

1. **Check token permissions:**
   - Token needs `repo` and `workflow` scopes
   - Fine-grained tokens need Actions and Workflows permissions

2. **Verify token in Jenkins:**
   ```bash
   # Check credential exists
   # Manage Jenkins → Credentials
   # Look for: github-pat-token
   ```

3. **Test token manually:**
   ```bash
   # In your terminal (not Jenkins)
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        https://api.github.com/repos/your-org/your-repo
   
   # Should return repo JSON, not 403
   ```

4. **Check repository name:**
   ```groovy
   // In Jenkinsfile line 34:
   GITHUB_REPO = 'pramodhkumars7/ai-jenkins-pipeline-triage'
   // Must match your actual repository
   ```

5. **Verify workflow file exists:**
   ```bash
   ls -la .github/workflows/
   # Should see: triage.yml
   ```

### Issue: Branches Don't Show in Parameters

**Symptoms:**
- Build with Parameters shows no GIT_BRANCH dropdown
- Or dropdown is empty

**Solutions:**

1. **Run build once first:**
   ```bash
   # Git Parameter plugin needs first run to discover branches
   # Click "Build Now" once
   # After #1 completes, branches will appear
   ```

2. **Verify Git Parameter plugin:**
   ```bash
   docker exec jenkins-local jenkins-plugin-cli --list | grep git-parameter
   # Should show: git-parameter x.x.x
   ```

3. **Check repository access:**
   ```bash
   docker exec jenkins-local bash -c "cd /workspace && git branch -r"
   # Should show all remote branches
   ```

4. **Job must use SCM:**
   - Pipeline definition must be "Pipeline script from SCM"
   - NOT "Pipeline script" (pasted code)

5. **Re-create job:**
   - Delete job
   - Create new one with correct SCM settings

### Issue: npm or Playwright Not Found

**Symptoms:**
```
npm: command not found
npx: command not found
```

**Solutions:**

1. **Rebuild Jenkins image:**
   ```bash
   cd jenkins
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

2. **Verify Node.js in container:**
   ```bash
   docker exec jenkins-local node --version
   docker exec jenkins-local npm --version
   docker exec jenkins-local npx playwright --version
   ```

3. **Check Dockerfile:**
   ```dockerfile
   # Ensure these lines exist in jenkins/Dockerfile:
   RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
   RUN apt-get install -y nodejs
   RUN npm install -g playwright
   RUN npx playwright install-deps
   ```

### Issue: Tests Pass but Should Fail

The demo tests are designed to fail for demonstration. If they pass:

1. **Check test files exist:**
   ```bash
   ls -la tests/
   # Should see: *.spec.js files
   ```

2. **Check test expectations:**
   ```javascript
   // tests/example.spec.js should have intentional failures
   ```

3. **For EKS scenarios:**
   ```bash
   # Ensure script exists
   ls -la scripts/gen_eks_log.py
   
   # Test manually
   python3 scripts/gen_eks_log.py CrashLoopBackOff
   ```

### Issue: Permission Denied Errors

**Symptoms:**
```
Permission denied: '/workspace/...'
```

**Solutions:**

1. **Fix volume permissions:**
   ```bash
   # In docker-compose.yml, ensure:
   user: root
   privileged: true
   ```

2. **Check file ownership:**
   ```bash
   docker exec jenkins-local ls -la /workspace
   # Files should be readable
   ```

3. **Fix locally:**
   ```bash
   # On your host machine
   chmod -R 755 .
   ```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Credentials not found: github-pat-token` | Credential ID mismatch | Check ID is exactly `github-pat-token` |
| `Repository not found: file:///workspace` | Wrong repo URL | Use `file:///workspace` (3 slashes) |
| `Script not found: jenkins/Jenkinsfile` | Wrong script path | Use `jenkins/Jenkinsfile` |
| `HTTP_CODE:403` | Token lacks permissions | Add `repo` and `workflow` scopes |
| `HTTP_CODE:404` | Repository not found | Check `GITHUB_REPO` in Jenkinsfile |
| `HTTP_CODE:422` | Invalid payload | Update to latest Jenkinsfile |
| `Container jenkins-local not found` | Container not running | `docker-compose up -d` |

---

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      Your Local Machine                       │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                Docker Container                        │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │           Jenkins LTS                        │    │  │
│  │  │           http://localhost:8080              │    │  │
│  │  │                                              │    │  │
│  │  │  ┌────────────────────────────────────┐     │    │  │
│  │  │  │  Pipeline Job                      │     │    │  │
│  │  │  │  • Checkout branch                 │     │    │  │
│  │  │  │  • Run tests (Playwright/EKS)      │     │    │  │
│  │  │  │  • Capture failure logs            │     │    │  │
│  │  │  │  • Sanitize sensitive data         │     │    │  │
│  │  │  └────────────────────────────────────┘     │    │  │
│  │  │                                              │    │  │
│  │  │  Bundled Tools:                             │    │  │
│  │  │  • Node.js 20.x                             │    │  │
│  │  │  • Playwright + Chromium                    │    │  │
│  │  │  • Python 3                                  │    │  │
│  │  │  • Git, GitHub CLI                          │    │  │
│  │  └──────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  Mounted Volumes:                                     │  │
│  │  • /workspace → Your project directory                │  │
│  │  • /var/jenkins_home → Jenkins data (persistent)      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            │ POST /repos/{owner}/{repo}/dispatches
                            │ Authorization: Bearer {GITHUB_TOKEN}
                            │ Body: { event_type, client_payload }
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                        GitHub Cloud                           │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              GitHub Actions Workflow                   │  │
│  │              (.github/workflows/triage.yml)            │  │
│  │                                                        │  │
│  │  Triggered by: repository_dispatch                    │  │
│  │  Event type: pipeline-failure                         │  │
│  │                                                        │  │
│  │  Steps:                                               │  │
│  │  1. Receive failure log from Jenkins                  │  │
│  │  2. Call Claude Sonnet 4.6 API                        │  │
│  │  3. Get RCA (Root Cause Analysis)                     │  │
│  │  4. Generate fix code                                 │  │
│  │  5. Create/update branch with fix                     │  │
│  │  6. Open Pull Request                                 │  │
│  │  7. Create/update GitHub Issue                        │  │
│  │  8. Send Teams notification                           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Outputs:                                                     │
│  • Pull Request with Claude's fix                             │
│  • GitHub Issue with RCA                                      │
│  • Code review comments                                       │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    Microsoft Teams (Optional)
                    Notification with PR link
```

### Data Flow

1. **Developer triggers Jenkins build:**
   - Selects branch and test category
   - Jenkins checks out code from `/workspace`

2. **Tests execute:**
   - Playwright: `npm install` → `npm test`
   - EKS: `python3 scripts/gen_eks_log.py`

3. **On failure:**
   - Jenkins captures complete output
   - Sanitizes logs (removes secrets, emails, tokens)
   - Creates JSON payload

4. **GitHub API call:**
   ```json
   {
     "event_type": "pipeline-failure",
     "client_payload": {
       "log": "sanitized failure log...",
       "category": "playwright-e2e",
       "job": "ci-pipeline",
       "source": "jenkins",
       "timestamp": "2024-05-19 10:30:00"
     }
   }
   ```

5. **GitHub Actions workflow:**
   - Receives event via `repository_dispatch`
   - Extracts failure log from payload
   - Calls Claude API with context
   - Claude analyzes and generates fix
   - Creates branch, commits fix, opens PR
   - Creates/updates Issue
   - Sends Teams notification

### Directory Structure

```
jenkins/
├── Dockerfile                 # Custom Jenkins image definition
├── docker-compose.yml         # Container orchestration
├── Jenkinsfile               # Pipeline script (version controlled)
├── README.md                 # This file
├── setup.sh                  # Automated setup script
└── init/                     # Jenkins startup scripts
    ├── 01-create-admin.groovy
    └── 02-configure-git.groovy

../                           # Project root (mounted as /workspace)
├── .env                      # GitHub token (not committed)
├── .github/workflows/
│   └── triage.yml           # GitHub Actions workflow
├── tests/                    # Playwright test files
├── scripts/
│   └── gen_eks_log.py       # EKS failure simulator
└── k8s/
    └── deployment.yaml      # Kubernetes manifest
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **CI/CD** | Jenkins LTS | Pipeline orchestration |
| **Container** | Docker | Isolated environment |
| **Runtime** | Node.js 20.x | JavaScript test execution |
| **Testing** | Playwright | E2E browser testing |
| **Simulation** | Python 3 | Generate Kubernetes logs |
| **VCS** | Git | Version control |
| **Cloud CI** | GitHub Actions | Triage workflow |
| **AI** | Claude Sonnet 4.6 | Code analysis & fixes |
| **Notification** | Teams Webhook | Alert delivery |

---

## 🛠️ Daily Usage

### Start Jenkins

```bash
cd jenkins
docker-compose start
```

### Stop Jenkins

```bash
cd jenkins
docker-compose stop
```

### Restart Jenkins

```bash
docker restart jenkins-local
```

### View Logs

```bash
# Real-time logs
docker logs -f jenkins-local

# Last 100 lines
docker logs --tail 100 jenkins-local
```

### Update Jenkinsfile

```bash
# Edit locally
nano jenkins/Jenkinsfile

# Changes take effect immediately (no restart needed)
# Just run new build
```

### Clean Slate

```bash
cd jenkins

# Remove everything (containers, volumes, data)
docker-compose down -v

# Start fresh
docker-compose up -d --build
```

---

## 📦 Maintenance

### Update Jenkins

```bash
cd jenkins

# Pull latest Jenkins LTS
docker-compose pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Backup Jenkins Data

```bash
# Jenkins data is in Docker volume
docker volume inspect jenkins_jenkins_home

# Backup
docker run --rm \
  -v jenkins_jenkins_home:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/jenkins-backup.tar.gz /data

# Restore (if needed)
docker run --rm \
  -v jenkins_jenkins_home:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/jenkins-backup.tar.gz -C /
```

### Monitor Disk Usage

```bash
# Check Docker disk usage
docker system df

# Clean unused images/containers
docker system prune -a
```

---

## 🤝 Team Collaboration

### Sharing Setup

Each team member should:

1. Clone repository
2. Create their own `.env` with their GitHub token
3. Run `setup.sh`
4. Configure Jenkins with their token
5. Create pipeline job

### Version Control

**What's committed:**
- ✅ `Dockerfile`
- ✅ `docker-compose.yml`
- ✅ `Jenkinsfile`
- ✅ `setup.sh`
- ✅ Init scripts

**What's NOT committed:**
- ❌ `.env` (tokens)
- ❌ `jenkins_home/` (Jenkins data)
- ❌ Test outputs

### Making Changes

```bash
# Edit Jenkinsfile
git checkout -b feature/update-pipeline
nano jenkins/Jenkinsfile

# Commit
git add jenkins/Jenkinsfile
git commit -m "feat: update pipeline to..."

# Push and create PR
git push origin feature/update-pipeline
```

---

## 📞 Support

### Debug Checklist

- [ ] Docker is running: `docker ps`
- [ ] Container is running: `docker ps | grep jenkins-local`
- [ ] Jenkins is accessible: http://localhost:8080
- [ ] Can login with admin/admin123
- [ ] GitHub token is added with ID `github-pat-token`
- [ ] Pipeline job exists
- [ ] Repository URL is `file:///workspace`
- [ ] Script Path is `jenkins/Jenkinsfile`
- [ ] First build has run (parameters discovered)

### Useful Commands

```bash
# Quick health check
docker ps | grep jenkins && echo "✓ Jenkins running" || echo "✗ Jenkins not running"

# Access container shell
docker exec -it jenkins-local bash

# Inside container, check mounts
ls -la /workspace
ls -la /var/jenkins_home

# Test git access
cd /workspace && git status

# Test Node.js
node --version
npm --version

# Test Playwright
npx playwright --version
```

### Get Help

- Check this README thoroughly
- Review console output for specific errors
- Search error messages in troubleshooting section
- Check GitHub Actions logs for triage workflow errors
- Review Jenkins system logs: Manage Jenkins → System Log

---

## 📚 Additional Resources

- [Jenkins Documentation](https://www.jenkins.io/doc/)
- [Docker Documentation](https://docs.docker.com/)
- [Playwright Documentation](https://playwright.dev/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Claude API Documentation](https://docs.anthropic.com/)

---

## ✅ Success Checklist

You've successfully set up the pipeline when:

- [ ] Jenkins accessible at http://localhost:8080
- [ ] Can login with admin credentials
- [ ] GitHub token added to Jenkins
- [ ] Pipeline job created
- [ ] First build runs successfully
- [ ] "Build with Parameters" shows branch dropdown
- [ ] Test build triggers and runs
- [ ] Console output shows sanitized logs
- [ ] GitHub Actions workflow triggers on failure
- [ ] Claude creates RCA and PR
- [ ] GitHub Issue is created
- [ ] Teams notification sent (if configured)

---

**Happy Testing!** 🚀

For issues or improvements, create an issue or PR on the repository.
