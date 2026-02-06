#!/usr/bin/env bash
set -euo pipefail

# CRON_SCHEDULE default: run daily at 09:00 UTC
CRON_SCHEDULE=${CRON_SCHEDULE:-0 9 * * *}

# The command to run - use docker path to python
CMD=${CRON_CMD:-"python -m app.main"}

# Write out a crontab
echo "${CRON_SCHEDULE} ${CMD} >> /app/state/cron.log 2>&1" > /tmp/crontab
crontab /tmp/crontab

# Start cron in the foreground (use -f where available)
# Note: on debian/ubuntu cron runs in foreground if -f is passed to cron
cron -f
