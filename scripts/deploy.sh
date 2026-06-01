#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Pulling latest code..."
git pull

echo "==> Building Docker image..."
docker build -t slack-coach:latest .

echo "==> Starting containers..."
docker compose up -d coach-socket coach-cron

echo "==> Done."
