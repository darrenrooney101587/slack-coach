# slack-coach

Fireflies-to-Slack meeting recap pipeline. When a meeting ends, Fireflies posts a webhook to this server, which fetches the transcript via the Fireflies GraphQL API, formats a recap as Slack Block Kit blocks, and routes it to the correct Slack channel or DM based on `routing.yml`.

## Project Structure

```
├── app/
│   ├── server.py         # Flask webhook handler (Fireflies + Slack actions)
│   ├── fireflies.py      # Fireflies GraphQL client and signature verification
│   ├── formatter.py      # Slack Block Kit formatter
│   ├── router.py         # routing.yml evaluation logic
│   ├── slack.py          # Slack chat.postMessage wrapper
│   ├── review.py         # Review mode state (hold / pop recap)
│   ├── votes.py          # Vote and feedback recording
│   ├── socket_server.py  # Slack Socket Mode handler (review approvals, voting)
│   └── entrypoint.sh     # Container mode selector (server / socket)
├── routing.yml           # Channel routing rules
├── docker-compose.yml    # Service definitions
├── Dockerfile
├── pyproject.toml
├── webhook_test.sh       # Local webhook test helper
└── docs/                 # Technical documentation
```

## Quick Start

```bash
# Install dependencies
poetry install

# Copy and populate environment variables
cp .env.example .env

# Run the webhook server locally
FLASK_DEBUG=1 poetry run flask --app app.server run --port 8080
```

To receive webhooks from Fireflies during local development, expose port 8080 with ngrok:

```bash
ngrok http 8080
```

Then set the ngrok URL as your webhook endpoint in the Fireflies dashboard (Settings > Webhooks).

## Prerequisites

- A Fireflies account with API access and a configured webhook
- A Slack App with `chat:write` bot scope and the bot invited to all target channels
- ngrok (or a reverse proxy) for local development

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot token (`xoxb-...`) with `chat:write` scope |
| `FIREFLIES_API_KEY` | Yes | Fireflies API key for fetching transcripts |
| `FIREFLIES_WEBHOOK_SECRET` | No | If set, incoming webhook signatures are verified |
| `SLACK_SIGNING_SECRET` | No | If set, incoming Slack action requests are verified |
| `REVIEW_MODE` | No | Set to `true` to hold recaps for reviewer approval before posting |
| `REVIEWER_USER_ID` | No | Slack user ID of the reviewer (required when `REVIEW_MODE=true`) |
| `SLACK_APP_TOKEN` | No | App-level token (`xapp-...`) required when `REVIEW_MODE=true` for Socket Mode |
| `ROUTING_CONFIG_FILE` | No | Path to routing config (default: `routing.yml` in repo root) |
| `STATE_DIR` | No | Directory for review mode and vote state files (default: `/app/state`) |

## Docker

Two services are available:

```bash
# Build the image
docker build -t slack-coach:latest .

# Webhook server only (standard mode)
docker compose up -d coach-server

# Webhook server + Socket Mode (required for review mode)
docker compose up -d coach-server coach-socket
```

- `coach-server` — Flask webhook receiver; handles Fireflies events and routes recaps to Slack
- `coach-socket` — Slack Socket Mode server; handles reviewer Approve/Skip actions and message voting

Both containers must share the same `STATE_DIR` volume when review mode is enabled.

## How It Works

### Fireflies Webhook Pipeline

1. Fireflies posts a webhook to `POST /webhooks/fireflies` when a meeting is summarized
2. The server fetches the full transcript from the Fireflies GraphQL API
3. The transcript's `title`, `summary.overview`, and `summary.action_items` are formatted into Slack Block Kit blocks
4. `routing.yml` rules are evaluated against the meeting title and organizer email to determine the target channel(s)
5. The recap is posted via `chat.postMessage` to each resolved channel or DM

### Review Mode

When `REVIEW_MODE=true`, step 5 is replaced by a human approval gate:

1. The recap is held in `held_recaps.json` under a UUID key
2. A DM is sent to `REVIEWER_USER_ID` with the full recap preview and **Approve** / **Skip** buttons
3. Clicking **Approve** posts the recap to the original target channel
4. Clicking **Skip** discards it silently

This requires `coach-socket` to be running to handle the button interactions.

### Slack Interactions

`coach-socket` handles three types of Slack button interactions via Socket Mode:

- **Recap review** — Approve or Skip a held recap from the reviewer DM
- **Feedback voting** — Thumbs up / thumbs down on a posted message; updates button state and records to `feedback_*.json`
- **Topic poll voting** — Vote for the next coaching topic; refreshes live vote counts and voter avatars on the message

## Testing Locally

`webhook_test.sh` sends a test webhook payload to the local server using a real meeting ID:

```bash
# Uses the default meeting ID embedded in the script
bash webhook_test.sh

# Pass a specific meeting ID
bash webhook_test.sh YOUR_MEETING_ID

# Target a different host
HOST=https://your-ngrok-url.ngrok.io bash webhook_test.sh YOUR_MEETING_ID
```

Ensure `FIREFLIES_API_KEY` and `SLACK_BOT_TOKEN` are set in your environment or `.env` file.

## Documentation

- **[Routing Configuration](docs/routing.md)** — How `routing.yml` works, match fields, regex patterns, and channel vs DM routing
- **[Deployment](docs/deployment.md)** — EC2 deployment with Docker and Fireflies webhook configuration
