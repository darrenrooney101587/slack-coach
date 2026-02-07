# Daily SQL Coach

A containerized job that calls AWS Bedrock (Claude) to generate a daily Postgres SQL optimization tip and posts it to Slack.

This README covers local development with Poetry, building and running the Docker image, running the Flask interactive receiver, and running the daily job via a containerized cron service (or ad-hoc).

Key repo files
- `app/main.py` - the job that generates content and posts to Slack
- `app/server.py` - a small Flask receiver to handle Slack interactive button callbacks and record votes
- `app/cron-runner.sh` - registers the crontab and starts cron in foreground
- `app/entrypoint.sh` - container entrypoint that selects `job`, `server`, or `cron` modes
- `Dockerfile` - builds the image using Poetry
- `docker-compose.yml` - composes `coach-server`, `coach-job`, and `coach-cron`
- `.env.example` - example environment file; copy to `.env` and fill in secrets

Quick overview
- Use Poetry for dependency management during development.
- Build a single Docker image that can run in three modes:
  - `job` — run the job once and exit
  - `server` — run the Flask receiver for Slack interactive events
  - `cron` — run cron and execute the job on the schedule in `CRON_SCHEDULE`
- Persist runtime state (votes, dedupe state, cron logs) on the host via `HOST_STATE_DIR` (mounted to `/app/state`).

Prerequisites
- Docker & Docker Compose installed on the host
- A Slack App with a Bot token and Interactivity enabled (for button callbacks)
- AWS access to Bedrock (either via instance role or exported env vars)

Using Poetry (development)

1. Install project dependencies with Poetry:

```bash
poetry install
```

2. Run the job locally:

```bash
# run the job once using Poetry environment
poetry run python app/main.py
```

3. Run the Flask interactive server locally for testing (use ngrok to expose to Slack):

```bash
poetry run python app/server.py
# then in another terminal, expose with ngrok:
# ngrok http 8080
```

Docker / Docker Compose (recommended for deployment)

1. Copy `.env.example` to `.env` and populate values (Slack tokens, signing secret, AWS info, HOST_STATE_DIR, etc.).

```bash
cp .env.example .env
# edit .env (SLACK_BOT_TOKEN, SLACK_CHANNEL_ID_VIEW (or legacy SLACK_CHANNEL_ID), SLACK_SIGNING_SECRET, AWS creds if needed)
```

Important env vars in `.env` (fill these in):
- `SLACK_BOT_TOKEN` — bot user token (xoxb-...)
- `SLACK_CHANNEL_ID_VIEW` — channel id where the Postgres "view" (database) team posts. `SLACK_CHANNEL_ID` remains supported for backward compatibility.
- `SLACK_SIGNING_SECRET` — used by the Flask receiver to verify Slack requests
- `AWS_REGION`, `BEDROCK_MODEL_ID` — Bedrock model and region
- Optional: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` if you want to provide explicit credentials
- `HOST_STATE_DIR` — host directory to persist `/app/state` (default `./state`)

NOTE: Some Docker Compose installations require Buildx to perform an image build via `docker compose build`. If your environment shows an error like:

```
compose build requires buildx 0.17.0 or later
```

you can work around this by building the image locally with `docker build` and then using `docker compose up` (compose will use the pre-built image and won't attempt to build). Example:

```bash
# Build image locally (from repo root)
docker build -t slack-coach:latest .

# Then start the services with compose which will use the existing image
docker compose up -d coach-server coach-cron
```

2. Build the Docker image with Compose (this uses the `Dockerfile` and Poetry inside the image):

```bash
docker compose build
```

3. Create the host state folder and ensure ownership:

```bash
mkdir -p ${HOST_STATE_DIR:-./state}
sudo chown "$(id -u):$(id -g)" ${HOST_STATE_DIR:-./state}
chmod 700 ${HOST_STATE_DIR:-./state}
```

4. Start services:
- Start the server (Flask receiver) and cron runner (scheduled job):

```bash
docker compose up -d coach-server coach-cron
```

- Run the job once (ad-hoc run):

```bash
docker compose run --rm coach-job
```

How the cron service works
- `coach-cron` runs the single image in `RUN_MODE=cron`.
- `CRON_SCHEDULE` in `.env` controls when the job runs (default `0 9 * * *`, which runs daily at 09:00 UTC).
- The cron job logs to `/app/state/cron.log` (host-mounted at `${HOST_STATE_DIR:-./state}/cron.log`).
- To change schedule, update `.env` and then restart the cron container:

```bash
docker compose restart coach-cron
```

State persistence and where data is stored
- The containers mount `HOST_STATE_DIR` from the host into `/app/state` inside the container.
- Files stored there:
  - `votes.json` — recorded votes from Slack interactive buttons
  - `last_sent.json` — dedupe state for last-sent date
  - `cron.log` — cron stdout/stderr from scheduled runs

Verify votes and logs

```bash
# list state files
ls -la ${HOST_STATE_DIR:-./state}

# pretty print votes
cat ${HOST_STATE_DIR:-./state}/votes.json | jq .

# view cron logs
tail -n 200 ${HOST_STATE_DIR:-./state}/cron.log
```

Slack App configuration notes
- In the Slack App config:
  - Add `chat:write` to Bot Token Scopes and reinstall the app
  - Enable Interactivity and set the Request URL to the public URL of your server (e.g., https://myhost/slack/actions). For local testing use ngrok.

Security & secrets
- Use secrets manager in production (do not check `.env` into git)
- Set `SLACK_SIGNING_SECRET` so the Flask receiver verifies incoming Slack requests

Handling credentials for Bedrock
- Preferred: run containers on EC2 with an instance role that has Bedrock permissions (no keys required)
- Alternative: set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (and optional `AWS_SESSION_TOKEN`) in `.env`.

Troubleshooting
- Read logs:

```bash
docker compose logs coach-server --tail 200
docker compose logs coach-cron --tail 200
```

- If the job reports `The security token included in the request is invalid.`, double-check the credentials you're using (either the explicit AWS env vars or the instance role / shared credentials).
- If you get `Failed to create state directory` on startup, ensure `HOST_STATE_DIR` on the host is writable by the container user (chown/chmod as needed).

Production notes & recommendations
- Persist the `HOST_STATE_DIR` to a stable host path or a mounted volume.
- For higher concurrency, consider replacing the JSON file votes store with SQLite (atomic writes) or a small DB.
- It's recommended to run `coach-cron` or scheduling in your orchestrator (e.g., Kubernetes CronJob) rather than running a long-lived containerized cron in production.

Support and next steps
- I can help convert the votes storage to SQLite and add an admin endpoint to query votes.
- I can update the job to capture Slack message `ts` and use it as the canonical `message_id` for vote aggregation.

---

If you'd like, I can also add a short `README_QUICKSTART.md` that contains only the minimal commands to get started locally with Docker Compose.
