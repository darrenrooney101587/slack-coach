#!/usr/bin/env bash
set -euo pipefail

RUN_MODE=${RUN_MODE:-server}

STATE_DIR=${STATE_DIR:-/state}
export STATE_DIR
mkdir -p "$STATE_DIR" 2>/dev/null || true

if [ "$RUN_MODE" = "server" ]; then
  echo "Starting Slack actions server (Flask) on port ${PORT:-8080}"
  exec python -m app.server
elif [ "$RUN_MODE" = "socket" ]; then
  echo "Starting Slack Socket Mode server"
  exec python -m app.socket_server
else
  echo "Unknown RUN_MODE: ${RUN_MODE}" >&2
  exit 1
fi
