#!/usr/bin/env bash
set -euo pipefail

# Choose mode: 'job' (default) runs the scheduled job; 'server' runs the Flask receiver; 'cron' starts cron
RUN_MODE=${RUN_MODE:-job}

# Ensure STATE_DIR env var exists and is writable; default to /app/state
STATE_DIR=${STATE_DIR:-/app/state}
export STATE_DIR

# Try to create the configured state dir; if that fails, silently fall back to /app/state or a temp dir.
if mkdir -p "$STATE_DIR" 2>/dev/null; then
  :
else
  echo "Warning: unable to create STATE_DIR='$STATE_DIR'; attempting fallback /app/state" >&2
  STATE_DIR=/app/state
  export STATE_DIR
  if mkdir -p "$STATE_DIR" 2>/dev/null; then
    echo "Using fallback STATE_DIR='$STATE_DIR'"
  else
    echo "Warning: unable to create fallback STATE_DIR; using ephemeral temp dir (dedupe state will not persist)" >&2
    STATE_DIR=$(mktemp -d)
    export STATE_DIR
  fi
fi

# Attempt to set ownership for state dir (ignore failures)
chown -R $(id -u):$(id -g) "$STATE_DIR" 2>/dev/null || true

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
