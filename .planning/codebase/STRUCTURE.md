# Codebase Structure

**Analysis Date:** 2026-03-26

## Directory Layout

```
slack-coach/
├── app/                    # Application code (Python modules)
│   ├── __init__.py
│   ├── main.py            # Job runner: generates content and posts to Slack
│   ├── server.py          # Flask app: receives Slack interactive callbacks
│   ├── socket_server.py   # Slack Bolt app: Socket Mode listener for interactions
│   ├── votes.py           # Vote persistence and aggregation logic
│   ├── entrypoint.sh      # Docker entrypoint: routes to job/server/cron/socket modes
│   └── cron-runner.sh     # Cron registration and startup script
├── tests/                  # Test suite
│   ├── conftest.py        # Pytest fixtures and configuration
│   ├── test_main.py       # Tests for job execution and content generation
│   ├── test_channel_isolation.py        # Tests for multi-channel vote isolation
│   ├── test_feedback_vote_separation.py # Tests for vote type separation (feedback vs topic votes)
│   ├── test_channel_dedupe_votes.py     # Tests for deduplication behavior
│   └── test_real_world_scenario.py      # Integration-style scenario tests
├── .env.example           # Template environment file (sample secrets and config)
├── environment.py         # Utility to load environment variables from .env
├── pyproject.toml         # Poetry project manifest (Python, dependencies, metadata)
├── poetry.lock            # Lock file for reproducible dependency versions
├── Dockerfile             # Multi-mode Docker image (job/server/cron/socket)
├── docker-compose.yml     # Compose file for coach-cron and coach-socket services
├── README.md              # User documentation (setup, deployment, troubleshooting)
├── .gitignore             # Git exclusion rules
├── build.sh               # Build script (wrapper for docker commands)
├── state/                 # Local state directory (mounted in Docker, not in git)
│   ├── votes_*.json       # Vote tallies by job and channel
│   ├── feedback_*.json    # Feedback tallies by job and channel
│   └── last_sent_*.json   # Dedupe state per job and channel
└── logs/                  # Log storage (generated at runtime)
```

## Directory Purposes

**app/:**
- Purpose: All application code — job execution, Slack integration, state management
- Contains: Python modules for different service modes and shared utilities
- Key files: `main.py` (entry point for jobs), `server.py` (Flask callback receiver), `votes.py` (state persistence)

**tests/:**
- Purpose: Test suite for job logic, vote isolation, deduplication, and integration scenarios
- Contains: Pytest-based tests using fixtures from `conftest.py`
- Key files: Integration tests in `test_real_world_scenario.py`, unit tests in `test_main.py`

**state/:**
- Purpose: Runtime state persistence (host-mounted volume in Docker)
- Contains: JSON files for votes, feedback, dedupe state, cron logs
- Generated: Yes (created by containers at runtime)
- Committed: No (in `.gitignore`)

**logs/:**
- Purpose: Log files generated at runtime
- Generated: Yes
- Committed: No (in `.gitignore`)

## Key File Locations

**Entry Points:**

- `app/main.py` — Job execution entry point; instantiates `DailyCoach` and runs pipeline
  - Can be run directly: `poetry run python app/main.py`
  - Or via Docker: `docker compose run --rm coach-job`
  - Arguments: `--view`, `--data-engineering`, `--all` to select which coaches to run

- `app/server.py` — Flask server for Slack interactive callbacks
  - Runs on port 8080 by default (configurable via `PORT` env var)
  - Single endpoint: `POST /slack/actions`
  - Startup: `poetry run python app/server.py` or Docker with `RUN_MODE=server`

- `app/socket_server.py` — Slack Bolt Socket Mode listener
  - No public HTTP endpoint required; connects via WebSocket
  - Requires `SLACK_APP_TOKEN` and `SLACK_BOT_TOKEN`
  - Startup: Docker with `RUN_MODE=socket`

**Configuration:**

- `.env` — Environment secrets and configuration (not in git, created from `.env.example`)
  - Critical: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID_VIEW`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `STATE_DIR`
  - Optional: `SLACK_CHANNEL_ID_DATA_ENG` for Data Engineering coach, `SLACK_SIGNING_SECRET` for request verification

- `environment.py` — Utility for loading `.env` file
  - Called at startup by `app/main.py` to populate `os.environ`
  - Handles `export` prefixes and comments

- `.env.example` — Template with all supported environment variables
  - Copy to `.env` and populate before running

**Core Logic:**

- `app/main.py:DailyCoach` — Class containing all job logic
  - Methods: `__init__()`, `check_dedupe()`, `update_dedupe_state()`, `get_topic()`, `get_next_topic_candidates()`, `generate_content()`, `post_to_slack()`, `run()`
  - Two instances created by `__main__`: one for Postgres coach, one for Data Engineering coach

- `app/votes.py` — Vote and feedback management
  - Functions: `record_vote()`, `get_vote_counts()`, `get_poll_details()`, `get_winning_next_topic()`
  - File organization: Per-job-per-channel separation using `_get_file_path()`
  - Vote types: `thumbs_up`, `thumbs_down`, `vote_next_topic`

- `app/server.py:slack_actions()` — Flask route handler
  - Verifies Slack signature, extracts payload, delegates to `votes.record_vote()`

- `app/socket_server.py` — Slack Bolt action handlers
  - Handlers: `handle_thumbs_up()`, `handle_thumbs_down()`, `handle_vote_next_topic()`
  - Additionally updates message UI with vote counts via `client.chat_update()`

**Testing:**

- `tests/conftest.py` — Pytest fixtures (temp state dirs, mock Slack tokens, etc.)
- `tests/test_main.py` — Tests for `DailyCoach` job execution, Bedrock calls, Slack posting
- `tests/test_channel_isolation.py` — Verify votes separated by job and channel
- `tests/test_feedback_vote_separation.py` — Verify feedback and topic votes stored separately
- `tests/test_channel_dedupe_votes.py` — Verify dedupe state separated by job and channel
- `tests/test_real_world_scenario.py` — End-to-end scenario tests (multi-coach, voting, winning topics)

**Orchestration:**

- `app/entrypoint.sh` — Docker entrypoint script
  - Routes to job/server/cron/socket based on `RUN_MODE` env var
  - Creates `STATE_DIR` if needed

- `app/cron-runner.sh` — Cron registration and startup
  - Registers `CRON_SCHEDULE` in crontab
  - Starts cron in foreground, logging to `STATE_DIR/cron.log`

- `Dockerfile` — Multi-stage Python image
  - Base: `python:3.11-slim`
  - Installs: Poetry, cron, curl, build tools
  - Sets up Poetry virtual environment, installs dependencies, copies app code
  - User: `appuser` (UID 1000) for security

- `docker-compose.yml` — Service definitions
  - `coach-cron`: Runs scheduled jobs (env: `RUN_MODE=cron`)
  - `coach-socket`: Runs Socket Mode listener (env: `RUN_MODE=socket`)
  - Both mount `HOST_STATE_DIR` to `/state` for persistence

## Naming Conventions

**Files:**

- Snake_case for Python modules: `main.py`, `socket_server.py`, `votes.py`
- Kebab-case for shell scripts: `entrypoint.sh`, `cron-runner.sh`
- Lowercase for directories: `app/`, `tests/`, `state/`, `logs/`

**Functions & Methods:**

- Snake_case for all functions and methods: `get_winning_next_topic()`, `check_dedupe()`, `update_dedupe_state()`
- Private functions prefixed with `_`: `_get_file_path()`, `_get_date()`, `_extract_meta_from_action()`

**Classes:**

- PascalCase: `DailyCoach`

**Environment Variables:**

- Uppercase with underscores: `SLACK_BOT_TOKEN`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `STATE_DIR`, `RUN_MODE`
- Prefixes group related vars: `SLACK_*` (Slack config), `AWS_*` (AWS config)

**State Files:**

- Pattern: `{type}_{job}_{channel}.json`
  - `votes_postgres_C123456.json` — Postgres job votes in channel C123456
  - `feedback_data_engineering_C234567.json` — Data Engineering feedback in channel C234567
  - `last_sent_postgres.json` — Legacy single-channel dedupe (fallback if no channel ID)

## Where to Add New Code

**New Feature in Job Pipeline:**
- Primary code: `app/main.py` — add method to `DailyCoach` class
- Tests: `tests/test_main.py` — add test case to verify behavior
- Example: To add custom topic filtering, add method `filter_topics()` to `DailyCoach` and call it in `get_topic()`

**New Coach Job (e.g., Security Coach):**
- Add topic list to `app/main.py`: `SECURITY_COACH_TOPICS = [...]`
- Instantiate in `__main__` block with new channel ID and role prompt
- Add env vars to `.env.example`: `SLACK_CHANNEL_ID_SECURITY`
- Add tests: `tests/test_main.py` — verify new coach runs independently

**New Interactive Endpoint:**
- If Flask: add route to `app/server.py`, handler extracts payload and calls appropriate function
- If Socket Mode: add action handler to `app/socket_server.py`, use `@app.action()` decorator
- Both: delegate vote recording to `votes.record_vote()`

**Shared Utilities:**
- Helper functions for common patterns: `app/votes.py` (vote operations) or new module `app/utils.py`
- Import in dependent modules: `from app.votes import record_vote`

**New Tests:**
- Test files follow pattern: `tests/test_*.py`
- Use fixtures from `conftest.py` (temp dirs, mock env vars)
- Run with: `poetry run pytest tests/` or `pytest` if in Poetry environment

## Special Directories

**state/ (Host-mounted Volume):**
- Purpose: Persistent storage for votes, feedback, dedupe state across container restarts
- Generated: Yes (created by containers at runtime)
- Committed: No (excluded in `.gitignore`)
- Contents: JSON state files, `cron.log`
- Volume mount: Docker Compose mounts `${HOST_STATE_DIR:-./state}` on host to `/app/state` in container

**.env (Environment Secrets):**
- Purpose: Store secrets and configuration
- Generated: No (created manually from `.env.example`)
- Committed: No (in `.gitignore`)
- Loaded by: `environment.py:load_env()` called at startup
- Contains: Slack tokens, AWS credentials, channel IDs, configuration flags

**logs/ (Runtime Logs):**
- Purpose: Archived logs from containers
- Generated: Yes (optional, for persistent logging)
- Committed: No (excluded in `.gitignore`)

---

*Structure analysis: 2026-03-26*
