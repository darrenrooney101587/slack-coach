#!/usr/bin/env bash
set -euo pipefail

# CRON_SCHEDULE default: run daily at 09:00 UTC
CRON_SCHEDULE=${CRON_SCHEDULE:-0 9 * * *}

# Helper to choose python binary if not provided in the command
choose_default_cmd() {
  if command -v python >/dev/null 2>&1; then
    echo "python -m app.main"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3 -m app.main"
  else
    echo "python -m app.main"
  fi
}

# Collect commands + schedules into arrays. Support multiple job-specific env vars.
declare -a SCHEDULES
declare -a CMDS

# Primary default entry
DEFAULT_CMD=${CRON_CMD:-"$(choose_default_cmd)"}
SCHEDULES+=("${CRON_SCHEDULE}")
CMDS+=("${DEFAULT_CMD}")

# Optional view-specific entry
if [ -n "${CRON_CMD_VIEW:-}" ]; then
  SCHEDULES+=("${CRON_SCHEDULE_VIEW:-${CRON_SCHEDULE}}")
  CMDS+=("${CRON_CMD_VIEW}")
fi

# Optional data-engineering-specific entry
if [ -n "${CRON_CMD_DATA_ENG:-}" ]; then
  SCHEDULES+=("${CRON_SCHEDULE_DATA_ENG:-${CRON_SCHEDULE}}")
  CMDS+=("${CRON_CMD_DATA_ENG}")
fi

# Sanitize and prepare final crontab content
CRONTAB_TMP=/tmp/crontab
: > "${CRONTAB_TMP}"
LOGFILE=/proc/1/fd/1

# Ensure /var/run exists and pid file exists
if [ ! -d /var/run ]; then
  mkdir -p /var/run || true
fi
: >/var/run/crond.pid 2>/dev/null || true
chown $(id -u):$(id -g) /var/run/crond.pid 2>/dev/null || true

# Function to sanitize a command (remove redirections)
sanitize_cmd() {
  local raw="$1"
  echo "${raw}" | sed -E 's/\s*(2>&1|>\>\s*[^ ]+|>\s*[^ ]+)\s*//g'
}

# Build crontab lines
for i in "${!CMDS[@]}"; do
  raw_cmd="${CMDS[$i]}"
  sched="${SCHEDULES[$i]}"
  sanitized=$(sanitize_cmd "${raw_cmd}")
  if [ "${sanitized}" != "${raw_cmd}" ]; then
    echo "[cron-runner] Warning: CRON_CMD contained shell redirection; stripped redirects to ensure output goes to container stdout" >> "${LOGFILE}" 2>&1 || true
  fi
  # Final line forces redirection to container stdout
  echo "${sched} ${sanitized} > /proc/1/fd/1 2>&1" >> "${CRONTAB_TMP}"
done

# Log the crontab we installed so it's visible in the mounted state dir
{
  echo "[cron-runner] Installed crontab at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[cron-runner] Entries:"
  cat "${CRONTAB_TMP}"
  echo "----"
} >> "${LOGFILE}" 2>&1 || true

crontab "${CRONTAB_TMP}" || {
  echo "[cron-runner] Failed to install crontab" >> "${LOGFILE}" 2>&1 || true
}

# Find cron binary robustly
CRON_BIN=""
if command -v cron >/dev/null 2>&1; then
  CRON_BIN=$(command -v cron)
elif command -v crond >/dev/null 2>&1; then
  CRON_BIN=$(command -v crond)
fi

if [ -z "${CRON_BIN}" ]; then
  echo "[cron-runner] Warning: cron binary not found in PATH. Attempting to run 'cron -f' anyway." >> "${LOGFILE}" 2>&1 || true
  CRON_BIN="cron"
else
  echo "[cron-runner] Using cron binary: ${CRON_BIN}" >> "${LOGFILE}" 2>&1 || true
fi

# Start cron in the foreground (use -f where available)
echo "[cron-runner] Starting cron (foreground) at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${LOGFILE}" 2>&1 || true
if [ -z "${DEBUG_CRON:-}" ]; then
  exec ${CRON_BIN} -f
else
  echo "[cron-runner] DEBUG_CRON set; not executing cron. Exiting after writing crontab." >> "${LOGFILE}" 2>&1 || true
  cat "${CRONTAB_TMP}" >> "${LOGFILE}" 2>&1 || true
  # Also print crontab to stdout for debugging in one-off containers
  echo "--- CRONTAB_CONTENT_START ---"
  cat "${CRONTAB_TMP}"
  echo "--- CRONTAB_CONTENT_END ---"
  exit 0
fi
