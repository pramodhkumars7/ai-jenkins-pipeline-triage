#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================"
echo "🚀 Setting up Local Jenkins Environment"
echo "   (Manual Image Pull Method)"
echo "================================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting."; exit 1; }
echo "✓ Docker and Docker Compose are installed"
echo ""

# Check .env file
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo "✓ .env file created. Please edit it with your credentials."
    else
        echo "❌ .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Check required environment variables
if [ -z "$GITHUB_TOKEN" ]; then
    echo "⚠️  GITHUB_TOKEN not set in .env file"
    read -p "Enter your GitHub Personal Access Token: " GITHUB_TOKEN
    echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> "$PROJECT_ROOT/.env"
fi

if [ -z "$GITHUB_REPO" ]; then
    echo "⚠️  GITHUB_REPO not set in .env file"
    read -p "Enter your GitHub repository (format: owner/repo): " GITHUB_REPO
    echo "GITHUB_REPO=$GITHUB_REPO" >> "$PROJECT_ROOT/.env"
fi

echo ""
echo "📥 Step 1: Pulling Jenkins base image from Docker Hub..."
echo "   (This may take 2-5 minutes depending on your network)"
cd "$SCRIPT_DIR"
docker pull jenkins/jenkins:lts

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Failed to pull Jenkins image from Docker Hub"
    echo ""
    echo "Possible solutions:"
    echo "  1. Check your internet connection"
    echo "  2. Disconnect from VPN and try again"
    echo "  3. Check Docker Desktop is running: docker ps"
    echo "  4. Try using Google DNS in Docker Desktop settings"
    echo "  5. See README.md (Troubleshooting section) for more solutions"
    exit 1
fi

echo "✓ Base image downloaded successfully"
echo ""

echo "🔧 Step 2: Building custom Jenkins image with Node.js and Playwright..."
echo "   (This should be faster since base image is cached)"
docker-compose build

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Failed to build custom Jenkins image"
    echo ""
    echo "Try building without cache:"
    echo "  cd jenkins && docker-compose build --no-cache"
    exit 1
fi

echo "✓ Custom image built successfully"
echo ""

echo "🚀 Step 3: Starting Jenkins container..."
docker-compose up -d

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Failed to start Jenkins container"
    echo ""
    echo "Check logs with:"
    echo "  cd jenkins && docker-compose logs"
    exit 1
fi

echo "✓ Container started"
echo ""

echo "⏳ Step 4: Waiting for Jenkins to initialize (30-60 seconds)..."
sleep 10

# Wait for Jenkins to be ready
COUNTER=0
MAX_ATTEMPTS=30
until docker-compose exec -T jenkins curl -s http://localhost:8080/login >/dev/null 2>&1; do
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -eq $MAX_ATTEMPTS ]; then
        echo "❌ Jenkins failed to start after $MAX_ATTEMPTS attempts"
        echo ""
        echo "Check logs with: cd jenkins && docker-compose logs"
        exit 1
    fi
    echo "Still waiting... ($COUNTER/$MAX_ATTEMPTS)"
    sleep 2
done

echo ""
echo "================================================"
echo "✅ Jenkins is ready!"
echo "================================================"
echo ""
echo "📝 Access Jenkins at: http://localhost:8080"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "🔑 Next steps:"
echo "   1. Log in to Jenkins"
echo "   2. Go to 'Manage Jenkins' → 'Credentials'"
echo "   3. Add a 'Secret text' credential:"
echo "      - ID: github-pat-token"
echo "      - Secret: $GITHUB_TOKEN"
echo ""
echo "   4. Create a new Pipeline job:"
echo "      - New Item → Pipeline"
echo "      - Pipeline script from SCM → Git"
echo "      - Repository URL: file:///workspace"
echo "      - Script Path: jenkins/Jenkinsfile"
echo ""
echo "📖 See complete guide: jenkins/README.md"
echo "🔧 Having issues? See README.md Troubleshooting section"
echo ""
echo "📊 Useful commands:"
echo "   View logs:    cd jenkins && docker-compose logs -f"
echo "   Stop Jenkins: cd jenkins && docker-compose stop"
echo "   Start Jenkins: cd jenkins && docker-compose start"
echo "   Remove setup: cd jenkins && docker-compose down -v"
echo ""
