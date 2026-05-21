#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Pulling latest code..."
git pull

echo "==> Building Docker image..."
docker build -t slack-coach:latest .

echo "==> Starting containers..."
docker compose up -d coach-server coach-socket

echo "==> Fetching ngrok URL..."
WEBHOOK_URL=""
for i in {1..10}; do
    WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | python3 -c "
import sys, json
tunnels = json.load(sys.stdin).get('tunnels', [])
url = next((t['public_url'] for t in tunnels if t['public_url'].startswith('https')), '')
print(url)
" 2>/dev/null || true)
    if [ -n "$WEBHOOK_URL" ]; then
        break
    fi
    echo "   waiting for ngrok... (${i}/10)"
    sleep 3
done

echo ""
if [ -z "$WEBHOOK_URL" ]; then
    echo "WARNING: ngrok is not running or URL is not available."
    echo "Start it with:  sudo systemctl start ngrok"
    echo "Then run:       scripts/get-ngrok-url.sh"
else
    echo "============================================================"
    echo "  Fireflies webhook URL:"
    echo "  ${WEBHOOK_URL}/webhooks/fireflies"
    echo "============================================================"
    echo "  Paste this into Fireflies > Settings > Integrations > Webhooks"
    echo ""
    echo "  Verify the server is responding:"
    echo "  curl ${WEBHOOK_URL}/webhooks/fireflies"
    echo "  (expect 400 missing_meeting_id — that means it is up)"
fi
