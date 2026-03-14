#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Setup GitHub Actions self-hosted runner
#  Run this once on the machine that will run deployments
# ═══════════════════════════════════════════════════════

set -e

RUNNER_DIR="$HOME/actions-runner"

# Detect OS and arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS-$ARCH" in
  darwin-arm64)  PLATFORM="osx-arm64" ;;
  darwin-x86_64) PLATFORM="osx-x64" ;;
  linux-aarch64) PLATFORM="linux-arm64" ;;
  linux-x86_64)  PLATFORM="linux-x64" ;;
  *) echo "Unsupported platform: $OS-$ARCH"; exit 1 ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║  GitHub Actions Runner Setup ($PLATFORM)     "
echo "╚══════════════════════════════════════════════╝"
echo ""

# Step 1: Get repo info
if [ -z "$1" ]; then
  echo "Usage: ./setup-runner.sh <GITHUB_RUNNER_TOKEN>"
  echo ""
  echo "Get your token from:"
  echo "  GitHub → Repo → Settings → Actions → Runners → New self-hosted runner"
  echo "  Copy the token from the ./config.sh command shown"
  exit 1
fi

TOKEN="$1"

# Detect repo URL from git remote
REPO_URL=$(git remote get-url origin 2>/dev/null | sed 's/\.git$//' | sed 's|git@github.com:|https://github.com/|')
if [ -z "$REPO_URL" ]; then
  echo "Could not detect repo URL. Run this from inside the git repo."
  exit 1
fi
echo "Repo: $REPO_URL"
echo ""

# Step 2: Download runner
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep '"tag_name"' | sed 's/.*"v\(.*\)".*/\1/')
DOWNLOAD_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${PLATFORM}-${RUNNER_VERSION}.tar.gz"

echo "── Downloading runner v${RUNNER_VERSION} ──"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

curl -sL "$DOWNLOAD_URL" -o actions-runner.tar.gz
tar xzf actions-runner.tar.gz
rm actions-runner.tar.gz
echo "Downloaded to $RUNNER_DIR"
echo ""

# Step 3: Configure
echo "── Configuring runner ──"
./config.sh --url "$REPO_URL" --token "$TOKEN" --name "$(hostname)" --labels "self-hosted,$PLATFORM" --unattended
echo ""

# Step 4: Install as service
echo "── Installing as service ──"
if [ "$OS" = "darwin" ]; then
  ./svc.sh install
  ./svc.sh start
  echo "Runner installed as macOS LaunchAgent (auto-starts on login)"
else
  sudo ./svc.sh install
  sudo ./svc.sh start
  echo "Runner installed as systemd service (auto-starts on boot)"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Runner is running! Check status at:"
echo "  GitHub → Repo → Settings → Actions → Runners"
echo "══════════════════════════════════════════════"
