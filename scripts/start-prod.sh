#!/bin/bash
# Start the pl-dashboard production server (app mode)
# Used by CI/CD to run the app directly without Docker

DEPLOY_DIR="/Users/lenin/Desktop/workspace/pl-auto"
BACKEND_DIR="$DEPLOY_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
ENV_FILE="$DEPLOY_DIR/.env"

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
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999
