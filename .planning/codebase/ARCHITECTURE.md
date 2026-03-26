# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Service-oriented with modular job execution and persistent state management.

The system follows a **three-mode service pattern** where a single Docker image runs as:
1. **Job** — one-off content generation and Slack posting
2. **Server** — Flask receiver for interactive Slack callbacks
3. **Cron** — scheduled job runner with persistent state

Each mode operates independently but shares core libraries for state persistence and vote management.

**Key Characteristics:**
- Single codebase, multiple deployment modes via environment variables
- Stateful operations persisted to JSON files in `STATE_DIR`
- Multi-coach support: separate "Postgres" and "Data Engineering" jobs can run to different Slack channels
- Two Slack integration patterns: webhook-based and bot-token-based
- Channel and job isolation for voting and deduplication

## Layers

**Job Layer (Content Generation):**
- Purpose: Generate daily tips using Claude/Bedrock and post to Slack
- Location: `app/main.py` (class `DailyCoach`)
- Contains: Topic selection, content generation via Bedrock, deduplication logic, Slack posting
- Depends on: AWS Bedrock client, Slack API (webhook or bot), votes module for topic selection
- Used by: Cron runner, ad-hoc job execution

**Server Layer (Interactive Callbacks):**
- Purpose: Receive and process Slack interactive button clicks (votes, feedback)
- Location: `app/server.py` (Flask app)
- Contains: Request signature verification, vote recording dispatch
- Depends on: Votes module for persistence
- Used by: Slack interactive request routing

**Socket Mode Server (Alternative Interactive Layer):**
- Purpose: Handle Slack interactions via Socket Mode (no public endpoint required)
- Location: `app/socket_server.py` (Slack Bolt app)
- Contains: Action handlers for thumbs up/down/next-topic votes, message UI updates with vote counts
- Depends on: Slack Bolt framework, votes module, user image fetching
- Used by: Alternative to Flask server for deployments without public HTTP endpoint

**State & Persistence Layer:**
- Purpose: Manage JSON-based vote tallies, dedupe state, feedback aggregation
- Location: `app/votes.py`
- Contains: Vote recording, feedback/vote separation, vote counting, next-topic winner selection
- Depends on: File system (json files in `STATE_DIR`)
- Used by: All other layers for state operations

**Environment Layer:**
- Purpose: Load environment variables from `.env` file
- Location: `environment.py`
- Contains: .env file parsing with export statement support
- Depends on: File system
- Used by: All modules on startup

**Configuration & Orchestration:**
- Location: `app/entrypoint.sh`, `app/cron-runner.sh`, `Dockerfile`, `docker-compose.yml`
- Contains: Multi-mode selection, state directory initialization, scheduling
- Entry point: `app/entrypoint.sh` checks `RUN_MODE` and routes to appropriate service

## Data Flow

**Content Generation & Posting (Job Execution):**

1. Job startup (`app/main.py:main()` or `DailyCoach.run()`)
2. Load environment and create `DailyCoach` instance
3. Check dedupe state: if message already sent today, exit
4. Select topic: check for winning voted topic from yesterday, fallback to random
5. Generate candidates (3 random topics for voting)
6. Invoke Bedrock with prompt to generate content (text + resource_url)
7. Post to Slack with blocks (header, body, vote buttons, feedback buttons)
8. Update dedupe state (date + content hash)
9. Exit

**Vote Recording & Aggregation:**

1. User clicks button in Slack message
2. Slack sends POST to `/slack/actions` (Flask) or triggers action handler (Socket Mode)
3. Request verified with HMAC signature
4. Action metadata extracted: message_id, topic, job, channel, candidate, user_id
5. Vote persisted to file based on vote type:
   - Feedback votes (thumbs_up/down) → `feedback_{job}_{channel}.json`
   - Topic votes (vote_next_topic) → `votes_{job}_{channel}.json`
6. Socket Mode additionally fetches user image and updates message UI with vote counts

**Topic Selection:**

1. Job queries previous day's votes via `get_winning_next_topic(yesterday, job, channel)`
2. Function reads `votes_{job}_{channel}.json` and counts votes for candidates matching date
3. Returns candidate with highest count (ties broken alphabetically)
4. Falls back to random topic if no winner or function unavailable

**State Management:**

State is organized by job and channel to support multi-coach isolation:
- `last_sent_{job}_{channel}.json` — today's send timestamp and content hash (dedupe)
- `votes_{job}_{channel}.json` — next-topic vote tallies per message
- `feedback_{job}_{channel}.json` — thumbs up/down feedback per message
- Legacy support: `last_sent_{job}.json` for single-channel deployments

## Key Abstractions

**DailyCoach Class:**
- Purpose: Encapsulates all job logic for generating and posting tips
- Examples: `DailyCoach("postgres", DEFAULT_TOPICS, ...)` and `DailyCoach("data_engineering", DATA_ENGINEERING_TOPICS, ...)`
- Pattern: Instantiated with job name, topic list, channel, role prompt, title; `run()` executes full pipeline
- Responsibilities: dedupe checking, topic selection, Bedrock invocation, Slack posting, state updates

**Vote Recording Functions:**
- `record_vote(payload, state_dir)` — Generic vote persistence with file selection based on job/channel/vote_type
- `get_winning_next_topic(date, state_dir, job_filter, channel_filter)` — Query winner from previous day
- Pattern: Payload dict drives both storage path and record structure

**Message Metadata:**
- Embedded in Slack button `value` field as JSON
- Contains: message_id, topic, job, channel, date, (optional) candidate
- Allows stateless reconstruction of context on vote callback

## Entry Points

**Job Execution:**
- Location: `app/main.py:main()` (if run as `__main__`)
- Triggers: `python app/main.py`, `poetry run python app/main.py`, Docker container with `RUN_MODE=job`
- Responsibilities: Parse arguments (`--view`, `--data-engineering`, `--all`), instantiate coaches, run job, handle errors

**Server (Flask):**
- Location: `app/server.py` (if run as `__main__`)
- Triggers: `python app/server.py`, Docker container with `RUN_MODE=server`
- Listens on port 8080 (configurable via `PORT` env var)
- Endpoint: `POST /slack/actions` — receives Slack interactive callbacks
- Responsibilities: Verify requests, extract vote data, delegate to votes module

**Socket Mode Server:**
- Location: `app/socket_server.py`
- Triggers: Docker container with `RUN_MODE=socket`
- Connections: Slack Socket Mode (requires `SLACK_APP_TOKEN` and `SLACK_BOT_TOKEN`)
- Responsibilities: Register action handlers, process votes, update message UI

**Cron Runner:**
- Location: `app/cron-runner.sh`
- Triggers: Docker container with `RUN_MODE=cron`
- Behavior: Registers `CRON_SCHEDULE` in crontab, starts cron in foreground
- Logs cron output to `STATE_DIR/cron.log`
- Responsibilities: Invoke job at scheduled intervals

## Error Handling

**Strategy:** Graceful degradation with logging. Errors stop execution (exit code 1 for jobs) but don't crash supporting services.

**Patterns:**

- **State Directory Fallback:** If `STATE_DIR` creation fails, attempt fallback to `/tmp` before disabling dedupe (`app/main.py:143-152`)
- **AWS Credential Retry:** If Bedrock fails with explicit AWS creds, retry with default boto3 credentials (`app/main.py:378-403`)
- **JSON Parsing Resilience:** Bedrock response may have wrapped JSON; unwrap if detected (`app/main.py:331-349`)
- **Slack Signing Verification:** If `SLACK_SIGNING_SECRET` not set, warn and skip verification (`app/server.py:16-17`)
- **Vote File Read Errors:** Treat missing/corrupt vote files as empty state, proceed safely (`app/votes.py:39-45`)
- **Socket Mode UI Updates:** Catch message update errors and log warnings without failing vote recording (`app/socket_server.py:145-146`)

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module with `StreamHandler` to stdout
- Configuration: Set via `logging.basicConfig()` in `app/main.py` and `app/socket_server.py`
- Pattern: Module-level logger `logger = logging.getLogger(__name__)` in each file
- Output: `[ISO_TIMESTAMP] - [module_name] - [LEVEL] - [message]`

**Validation:**
- Environment variables checked at instance initialization (e.g., `AWS_REGION`, `BEDROCK_MODEL_ID`, `SLACK_BOT_TOKEN`)
- Raises `ValueError` if required config missing (`app/main.py:118-130`)
- Vote payload validation: JSON parsing with try-catch, fallback to empty dict on parse error

**Authentication & Security:**
- **Slack:** HMAC signature verification on incoming requests (`app/server.py:20-35`)
  - Header: `X-Slack-Request-Timestamp` and `X-Slack-Signature` (v0 scheme)
  - Timestamp validation: reject if request >5 min old
- **AWS:** Bedrock client configured with explicit creds (if provided) or default boto3 chain (instance role, shared credentials, env vars)
- Secrets: `.env` file excluded from git; `.env.example` provided as template

**State Consistency:**
- JSON files read with error handling; corrupt files treated as empty state
- Dedupe state file-per-job-per-channel prevents double-posting across multi-channel deployments
- Vote counts aggregated on-read; no locking (assumes single writer per state file via container isolation)

---

*Architecture analysis: 2026-03-26*
