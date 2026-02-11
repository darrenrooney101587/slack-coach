#!/usr/bin/env bash
set -euo pipefail

RUN_MODE=${RUN_MODE:-job}

STATE_DIR=${STATE_DIR:-/state}
export STATE_DIR
mkdir -p "$STATE_DIR" 2>/dev/null || true

if [ "$RUN_MODE" = "server" ]; then
  echo "Starting Slack actions server (Flask) on port ${PORT:-8080}"
  exec python -m app.server
elif [ "$RUN_MODE" = "cron" ]; then
  echo "Starting cron runner"
  exec /app/app/cron-runner.sh
elif [ "$RUN_MODE" = "socket" ]; then
  echo "Starting Slack Socket Mode server"
  exec python -m app.socket_server
else
  echo "Starting SQL coach job runner"
  exec python -m app.main "$@"
fi
