# External Integrations

**Analysis Date:** 2026-03-26

## APIs & External Services

**AI/ML:**
- AWS Bedrock - LLM invocation for content generation
  - SDK/Client: `boto3` (1.34.0)
  - Auth: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (optional)
  - Model ID: `BEDROCK_MODEL_ID` env var (e.g., `anthropic.claude-v2`)
  - Region: `AWS_REGION` env var
  - Used in: `app/main.py` DailyCoach.generate_content() (line 321-405)

**Messaging:**
- Slack API (two integration modes)
  - **Webhook Mode** (`SLACK_MODE=webhook`):
    - Endpoint: `https://hooks.slack.com/services/...` (via `SLACK_WEBHOOK_URL` env var)
    - Used in: `app/main.py` DailyCoach.post_to_slack() (line 480)
  - **Bot Mode** (`SLACK_MODE=bot`):
    - Token: `SLACK_BOT_TOKEN` env var
    - App Token: `SLACK_APP_TOKEN` env var (required for Socket Mode)
    - Endpoints: `https://slack.com/api/chat.postMessage` (line 599)
    - Used in: `app/main.py` DailyCoach.post_to_slack() bot branch (line 598-611)
    - Socket Mode handlers: `app/socket_server.py` (lines 21, 297)

## Data Storage

**State/Persistence:**
- File-based state management (local filesystem only)
  - Location: `/app/state` (configurable via `STATE_DIR` env var)
  - Dedupe tracking: `last_sent_{job}_{channel}.json` or `last_sent_{job}.json`
    - Tracks: `last_sent_date`, `last_message_hash`
  - Vote tracking: `votes_{job}_{channel}.json` or `votes_{job}.json`
    - Tracks: "vote_next_topic" votes with candidates and users
  - Feedback tracking: `feedback_{job}_{channel}.json` or `feedback_{job}.json`
    - Tracks: "thumbs_up"/"thumbs_down" reactions with user data
  - Used in: `app/main.py` (dedupe) and `app/votes.py` (voting/feedback)

**Databases:**
- None - state is file-based JSON

**File Storage:**
- Local filesystem only - no cloud storage integration

**Caching:**
- None detected

## Authentication & Identity

**Auth Provider:**
- Custom Slack request verification (webhook signature validation)
  - Implementation: HMAC-SHA256 validation in `app/server.py` verify_slack_request() (line 20-35)
  - Secret: `SLACK_SIGNING_SECRET` env var
  - Prevents replay attacks (timestamp check: 5-minute window)

**Bot Authentication:**
- Slack Bearer token authentication for bot mode
  - Header: `Authorization: Bearer {SLACK_BOT_TOKEN}`
  - Used in: `app/main.py` DailyCoach.post_to_slack() bot branch (line 486)

**AWS Authentication:**
- IAM credentials (explicit or default boto3 chain)
  - Explicit: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
  - Fallback: Default boto3 credentials from environment or instance profile
  - Credential error handling: Auto-fallback to default credentials on failure (line 378-403)

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- Python stdlib logging (`logging` module)
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Handler: `StreamHandler` to stdout
  - Used throughout: `app/main.py`, `app/socket_server.py`, `app/votes.py`
  - Log level: `INFO` by default

**Debugging:**
- Dry-run modes via env vars:
  - `DRY_RUN=1` - Skip Bedrock invocation, return canned content
  - `SLACK_DRY_RUN=1` - Log payload instead of posting to Slack

## CI/CD & Deployment

**Hosting:**
- Docker container (OCI-compliant)
- Deployment modes:
  - Standalone job execution (cron or one-off)
  - Flask server (webhook handlers)
  - Slack Socket Mode server (interactive handlers)
  - Cron job scheduler (in-container cron daemon)

**CI Pipeline:**
- None detected (no GitHub Actions, Jenkins, GitLab CI config)

**Container Registry:**
- Not specified (can be pushed to any OCI registry)

## Environment Configuration

**Required env vars:**

**AWS:**
- `AWS_REGION` - AWS region for Bedrock (e.g., `us-east-1`)
- `BEDROCK_MODEL_ID` - Model ID to invoke (e.g., `anthropic.claude-v2`)

**Slack Channel Configuration:**
- `SLACK_CHANNEL_ID_VIEW` - Channel ID for Postgres coach (falls back to `SLACK_CHANNEL_ID`)
- `SLACK_CHANNEL_ID_DATA_ENG` - Channel ID for Data Engineering coach (optional)

**Slack Mode Selection:**
- `SLACK_MODE` - `webhook` or `bot` (default: `webhook`)

**Slack Webhook Mode:**
- `SLACK_WEBHOOK_URL` - Webhook URL for posting (required if `SLACK_MODE=webhook`)

**Slack Bot Mode:**
- `SLACK_BOT_TOKEN` - Bot user token (required if `SLACK_MODE=bot`)
- `SLACK_APP_TOKEN` - App-level token for Socket Mode (required if `SLACK_MODE=bot`)
- `SLACK_SIGNING_SECRET` - Signing secret for request verification (optional, disables validation if unset)

**Optional env vars:**
- `AWS_ACCESS_KEY_ID` - Override default boto3 credentials (optional)
- `AWS_SECRET_ACCESS_KEY` - Override default boto3 credentials (optional)
- `AWS_SESSION_TOKEN` - STS session token (optional)
- `STATE_DIR` - Directory for vote/dedupe storage (default: `/app/state`)
- `TEMPERATURE` - Bedrock Claude temperature (default: `0.4`, float 0-1)
- `MAX_TOKENS` - Bedrock max output tokens (default: `450`, int)
- `DEDUPE_ENABLED` - Enable message deduplication (default: `true`)
- `TITLE_SUBTITLE` - Slack message subtitle text
- `TZ` - Timezone for date calculations (default: `UTC`)
- `TOPIC_MODE` - Topic selection strategy (default: `rotation`, unused in current code)
- `CURRICULUM_FILE` - Path to YAML curriculum file (default: `/app/curriculum.yml`)
- `DRY_RUN` - Skip Bedrock invocation (set to `1` to enable)
- `SLACK_DRY_RUN` - Skip Slack posting (set to `1` to enable)
- `PORT` - Flask server port (default: `8080`)
- `RUN_MODE` - Docker entrypoint mode: `job`, `server`, `cron`, `socket` (default: `job`)
- `CRON_SCHEDULE` - Cron schedule expression (default: `*/10 * * * *`)
- `CRON_CMD` - Command to run on cron schedule (default: `python -m app.main --all`)
- `MIGRATE_LEGACY_DEDUPE` - Migrate old dedupe files to channel-aware format (set to `1`)

**Secrets location:**
- `.env` file in project root (local) or via env vars in production
- Never committed (`.gitignore` includes `.env`)

## Webhooks & Callbacks

**Incoming (Flask server):**
- POST `/slack/actions` - Handles Slack interactive message actions (button clicks)
  - Handler: `app/server.py` slack_actions() (line 45-94)
  - Payload format: Slack interactive message payload (form-encoded JSON)
  - Actions processed: `vote_next_topic_*`, `thumbs_up`, `thumbs_down`
  - Response: Ephemeral JSON response with vote confirmation

**Outgoing (Slack API calls):**
- Webhook posts to `SLACK_WEBHOOK_URL` (Slack API)
- Direct API calls to `https://slack.com/api/chat.postMessage` (bot mode)
  - Called from: `app/main.py` DailyCoach.post_to_slack() (line 598-611)
- User info fetch: `slack_bolt.App.client.users_info()` (Socket Mode handler)
  - Called from: `app/socket_server.py` _get_user_image() (line 40)
- Message updates: `slack_bolt.App.client.chat_update()` (Socket Mode handler)
  - Called from: `app/socket_server.py` handlers (line 142, 198, 290)

**Socket Mode (WebSocket-based):**
- Real-time event subscription (alternative to webhooks)
- Handler: `app/socket_server.py` SocketModeHandler (line 297)
- Requires: `SLACK_APP_TOKEN` for connection

---

*Integration audit: 2026-03-26*
