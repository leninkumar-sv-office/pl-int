#!/bin/bash
# Stop and remove pl-dashboard container + image
docker rm -f pl-dashboard 2>/dev/null || true
cd "$(dirname "$0")/.." && docker compose down --rmi all --remove-orphans 2>/dev/null || true
echo "Container stopped and removed"
