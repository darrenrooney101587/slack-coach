#!/usr/bin/env bash
# Test the Fireflies webhook locally without waiting for a real event.
# Uses a real meeting_id so the server will fetch the transcript from the Fireflies API.
# Replace MEETING_ID with any valid meeting ID from your Fireflies account.

MEETING_ID=${1:-"01KMJYXW64TE021AB3APV5JNCV"}
HOST=${HOST:-"http://localhost:8080"}

curl -v -X POST "${HOST}/webhooks/fireflies" \
  -H "Content-Type: application/json" \
  -d "{
    \"meeting_id\": \"${MEETING_ID}\",
    \"event\": \"meeting.summarized\",
    \"timestamp\": $(date +%s000)
  }"
