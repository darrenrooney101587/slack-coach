#!/usr/bin/env bash
set -euo pipefail

RUN_MODE=${RUN_MODE:-socket}

STATE_DIR=${STATE_DIR:-/state}
export STATE_DIR
mkdir -p "$STATE_DIR" 2>/dev/null || true

if [ "$RUN_MODE" = "socket" ]; then
  echo "Starting Slack Socket Mode server"
  exec python -m app.socket_server
elif [ "$RUN_MODE" = "job" ]; then
  echo "Running daily coach job"
  exec python -m app.main
else
  echo "Unknown RUN_MODE: ${RUN_MODE}" >&2
  exit 1
fi
