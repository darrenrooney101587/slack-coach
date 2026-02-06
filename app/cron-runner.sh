#!/usr/bin/env bash
set -euo pipefail

# CRON_SCHEDULE default: run daily at 09:00 UTC
CRON_SCHEDULE=${CRON_SCHEDULE:-0 9 * * *}

# The command to run - use docker path to python
CMD=${CRON_CMD:-"python -m app.main"}

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
echo "${CRON_SCHEDULE} ${CMD} >> ${STATE_DIR:-/state}/cron.log 2>&1" > /tmp/crontab
crontab /tmp/crontab

# Start cron in the foreground (use -f where available)
# Note: on debian/ubuntu cron runs in foreground if -f is passed to cron
cron -f
