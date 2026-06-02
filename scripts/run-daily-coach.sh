#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "[$(date)] Starting daily coach job (one-shot)"
docker compose run --rm -e RUN_MODE=job --user root coach-cron
echo "[$(date)] Daily coach job complete"
