#!/usr/bin/env bash
set -euo pipefail

CRON_SCHEDULE="${CRON_SCHEDULE:-*/10 * * * *}"
CRON_CMD="${CRON_CMD:-python -m app.main --all}"

CRON_SCHEDULE="${CRON_SCHEDULE#\"}"; CRON_SCHEDULE="${CRON_SCHEDULE%\"}"
CRON_SCHEDULE="${CRON_SCHEDULE#\'}"; CRON_SCHEDULE="${CRON_SCHEDULE%\'}"
CRON_CMD="${CRON_CMD#\"}"; CRON_CMD="${CRON_CMD%\"}"
CRON_CMD="${CRON_CMD#\'}"; CRON_CMD="${CRON_CMD%\'}"

ENV_FILE=/tmp/cron.env
: > "${ENV_FILE}"
while IFS='=' read -r name value; do
  # Skip empty names or underscore
  [ -z "$name" ] && continue
  [ "$name" = "_" ] && continue
  # Write as export NAME='value' with single quotes escaped
  escaped_value="${value//\'/\'\\\'\'}"
  echo "export ${name}='${escaped_value}'" >> "${ENV_FILE}"
done < <(printenv)

CRONTAB_FILE=/tmp/crontab
cat > "${CRONTAB_FILE}" <<EOF
${CRON_SCHEDULE} . ${ENV_FILE}; cd /app && ${CRON_CMD} > /proc/1/fd/1 2>&1
EOF

echo "[cron] Schedule: ${CRON_SCHEDULE}"
echo "[cron] Command:  ${CRON_CMD}"
echo "[cron] Installing crontab..."
crontab "${CRONTAB_FILE}"

echo "[cron] Starting cron in foreground"
exec cron -f
