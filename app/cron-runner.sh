#!/usr/bin/env bash
set -euo pipefail

# CRON_SCHEDULE default: run daily at 09:00 UTC
CRON_SCHEDULE=${CRON_SCHEDULE:-0 9 * * *}

# The command to run - prefer python if available, fall back to python3
if [ -z "${CRON_CMD:-}" ]; then
  if command -v python >/dev/null 2>&1; then
    CMD_DEFAULT="python -m app.main"
  elif command -v python3 >/dev/null 2>&1; then
    CMD_DEFAULT="python3 -m app.main"
  else
    # Last resort: keep the generic python command; cron will log an error if missing
    CMD_DEFAULT="python -m app.main"
  fi
  CMD=${CRON_CMD:-"${CMD_DEFAULT}"}
else
  CMD=${CRON_CMD}
fi

# Sanitize CMD: remove any explicit shell redirects so we can force logs to /proc/1/fd/1
# This removes occurrences of '>', '>>', and '2>&1' and their following targets.
CMD_SANITIZED=$(echo "${CMD}" | sed -E 's/\s*(2>&1|>\>\s*[^ ]+|>\s*[^ ]+)\s*//g')
if [ "${CMD_SANITIZED}" != "${CMD}" ]; then
  echo "[cron-runner] Warning: CRON_CMD contained shell redirection; stripped redirects to ensure output goes to container stdout" >> /proc/1/fd/1 2>&1 || true
  CMD=${CMD_SANITIZED}
fi

# Log to container stdout (PID 1 fd 1) so it shows in docker logs
LOGFILE=/proc/1/fd/1

# Ensure /var/run and the cron pid file exist and are writable if possible.
# This helps when the container runs as root (we can chown) or when it runs as a host UID
# that already has write perms to /var/run.
if [ ! -d /var/run ]; then
  mkdir -p /var/run || true
fi
# Create a pid file if possible and attempt to set ownership to the current user.
: >/var/run/crond.pid 2>/dev/null || true
chown $(id -u):$(id -g) /var/run/crond.pid 2>/dev/null || true

# Write out a crontab
# sending to /proc/1/fd/1 makes it show up in 'docker logs'
echo "${CRON_SCHEDULE} ${CMD} > /proc/1/fd/1 2>&1" > /tmp/crontab

# Log the crontab we installed so it's visible in the mounted state dir
{
  echo "[cron-runner] Installed crontab at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[cron-runner] CRON_SCHEDULE: ${CRON_SCHEDULE}"
  echo "[cron-runner] CMD: ${CMD}"
  echo "[cron-runner] /tmp/crontab contents:"
  cat /tmp/crontab
  echo "----"
} >> "${LOGFILE}" 2>&1 || true

crontab /tmp/crontab || {
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
# Note: on debian/ubuntu cron runs in foreground if -f is passed to cron
echo "[cron-runner] Starting cron (foreground) at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${LOGFILE}" 2>&1 || true
exec ${CRON_BIN} -f
