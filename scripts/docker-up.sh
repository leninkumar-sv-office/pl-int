#!/bin/bash
# Build and start the pl-dashboard Docker container
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Ensure .env exists
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Create one with:"
  echo "  ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN,"
  echo "  ZERODHA_USER_ID, ZERODHA_PASSWORD, ZERODHA_TOTP_SECRET,"
  echo "  AUTH_MODE, GOOGLE_CLIENT_ID, ALLOWED_EMAILS,"
  echo "  GOOGLE_CLIENT_SECRET, GOOGLE_DRIVE_DUMPS_FOLDER_ID"
  exit 1
fi

# Stop and remove existing container (from any directory)
docker rm -f pl-dashboard 2>/dev/null || true
docker compose down --rmi all --remove-orphans 2>/dev/null || true

# Build and start — .env is auto-loaded by docker compose
docker compose up -d --build
echo "Container started. Health: http://localhost:8000/health"
