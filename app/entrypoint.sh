#!/usr/bin/env bash
set -euo pipefail

# Choose mode: 'job' (default) runs the scheduled job; 'server' runs the Flask receiver; 'cron' starts cron
RUN_MODE=${RUN_MODE:-job}

# Ensure STATE_DIR env var exists and is writable; default to /app/state
STATE_DIR=${STATE_DIR:-/app/state}
export STATE_DIR
mkdir -p "$STATE_DIR"
chown -R $(id -u):$(id -g) "$STATE_DIR" || true

if [ "$RUN_MODE" = "server" ]; then
  echo "Starting Slack actions server (Flask) on port ${PORT:-8080}"
  exec python -m app.server
elif [ "$RUN_MODE" = "cron" ]; then
  echo "Starting cron runner"
  exec /app/app/cron-runner.sh
else
  echo "Starting SQL coach job runner"
  exec python -m app.main
fi
