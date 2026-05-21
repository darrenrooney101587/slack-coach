#!/usr/bin/env bash
set -euo pipefail

URL=$(curl -s http://localhost:4040/api/tunnels \
    | python3 -c "
import sys, json
tunnels = json.load(sys.stdin).get('tunnels', [])
url = next((t['public_url'] for t in tunnels if t['public_url'].startswith('https')), '')
print(url)
" 2>/dev/null || true)

if [ -z "$URL" ]; then
    echo "ngrok is not running. Start it with: sudo systemctl start ngrok" >&2
    exit 1
fi

echo "${URL}/webhooks/fireflies"
