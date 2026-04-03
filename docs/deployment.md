# Deployment

This guide covers deploying the Fireflies recap pipeline on an EC2 instance using Docker. Only `coach-server` is needed for this use case.

## Prerequisites

- Docker installed on the host
- The host's port 8080 reachable from the internet, or a reverse proxy configured in front of it
- A Fireflies account with permission to configure webhooks
- A Slack App with `chat:write` bot scope

## 1. Build the Image

Clone the repo onto the host and build the image:

```bash
git clone <repo-url> slack-coach
cd slack-coach
docker build -t slack-coach:latest .
```

## 2. Create the Environment File

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SLACK_BOT_TOKEN=xoxb-...
FIREFLIES_API_KEY=...
FIREFLIES_WEBHOOK_SECRET=...   # optional but recommended
```

See the README for the full list of environment variables.

## 3. Start the Server

```bash
docker compose up -d coach-server
```

This starts `coach-server` with `RUN_MODE=server`, which runs the Flask application on port 8080. The container will restart automatically unless explicitly stopped.

To verify it is running:

```bash
docker compose logs coach-server --tail 50
curl http://localhost:8080/webhooks/fireflies
```

The `curl` command should return a `400` with `{"ok": false, "error": "missing_meeting_id"}` — that confirms the server is up and routing is reachable.

## 4. Expose the Endpoint

Fireflies requires a publicly reachable HTTPS URL for the webhook.

### Option A: ngrok (quick setup, not for permanent production)

```bash
ngrok http 8080
```

Copy the `https://` forwarding URL from the ngrok output.

### Option B: Reverse proxy (recommended for production)

Configure nginx or caddy to proxy HTTPS traffic to `localhost:8080`. The Flask app uses `ProxyFix` middleware so it handles `X-Forwarded-For` and `X-Forwarded-Proto` headers correctly.

Example nginx snippet:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### EC2 Security Group

Ensure the EC2 security group allows inbound HTTPS (port 443) from `0.0.0.0/0`, or inbound on port 8080 if you are not using a reverse proxy.

## 5. Configure the Fireflies Webhook

1. Go to the Fireflies dashboard: Settings > Integrations > Webhooks
2. Add a new webhook with the URL: `https://your-host/webhooks/fireflies`
3. Select the `meeting.summarized` event (or equivalent — the server logs the raw event type and proceeds regardless)
4. If you set `FIREFLIES_WEBHOOK_SECRET` in `.env`, copy the same secret into the Fireflies webhook secret field

After the next meeting is processed by Fireflies, the recap will be posted to Slack according to `routing.yml`.

## 6. Invite the Bot to Channels

The Slack bot must be a member of every channel listed in `routing.yml`. For private channels, invite the bot manually:

```
/invite @your-bot-name
```

Routing to a user ID (DM) does not require an invite — the bot can DM any user in the workspace.

## Updating routing.yml

After editing `routing.yml` on the host, restart the server to pick up the changes:

```bash
docker compose restart coach-server
```

## Logs

```bash
# Tail server logs
docker compose logs coach-server -f

# Last 200 lines
docker compose logs coach-server --tail 200
```

Key log messages:

| Message | Meaning |
|---|---|
| `fireflies_webhook: resolved channels=...` | Routing succeeded — shows which channel(s) will receive the post |
| `fireflies_webhook: no_routing_target` | No rule matched and no `default_channel` set in `routing.yml` |
| `fireflies_webhook: transcript_fetch_failed` | The Fireflies API did not return a transcript for the meeting ID |
| `fireflies_webhook: missing_required_fields` | The transcript has no `overview`, `bullet_gist`, or `action_items` — nothing to post |
| `Slack API error: not_in_channel` | The bot is not a member of the target channel — invite it |

## Updating the Application

```bash
git pull
docker build -t slack-coach:latest .
docker compose up -d coach-server
```

The old container is replaced with the new image.
