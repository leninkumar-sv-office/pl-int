#!/bin/bash
# Start the pl-dashboard production server
# Used by LaunchAgent to run the app independently of GitHub Actions runner

DEPLOY_DIR="/Users/lenin/Desktop/workspace/pl-auto"
BACKEND_DIR="$DEPLOY_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
ENV_FILE="$DEPLOY_DIR/.env"
LOG_FILE="$DEPLOY_DIR/app.log"

cd "$BACKEND_DIR" || exit 1

# Activate venv
source "$VENV_DIR/bin/activate" || exit 1

# Load environment variables
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

# Run uvicorn (foreground — launchd manages stdout/stderr)
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# test run 2
# test run 3
# test run 4
