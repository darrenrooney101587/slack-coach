#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "[$(date)] Starting daily coach job"
docker compose --profile cron run --rm coach-cron
echo "[$(date)] Daily coach job complete"
