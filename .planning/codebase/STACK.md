# Technology Stack

**Analysis Date:** 2026-03-26

## Languages

**Primary:**
- Python 3.10+ - Core application logic, coaching engine, vote processing

## Runtime

**Environment:**
- Python 3.11-slim (Docker)
- Unix-like (Linux/macOS)

**Package Manager:**
- Poetry 1.8.0
- Lockfile: `poetry.lock` (present)

## Frameworks

**Core:**
- Flask 2.3.3 - HTTP server for Slack webhook/interactive button handlers (`app/server.py`)
- slack-bolt ^1.20.0 - Slack bot framework for Socket Mode handlers (`app/socket_server.py`)

**Testing:**
- pytest ^7.4.0 - Test runner, configured via conftest in `tests/conftest.py`
- pytest-mock ^3.11.1 - Mocking utilities for tests

**Build/Dev:**
- pre-commit ^3.4.0 - Git hook framework
- detect-secrets ^1.4.0 - Secret detection in commits

## Key Dependencies

**Critical:**
- boto3 1.34.0 - AWS SDK for Bedrock model invocation (`app/main.py` line 8, 168-172)
- requests 2.31.0 - HTTP client for Slack API calls (`app/main.py` lines 480, 598-602)
- PyYAML 6.0.0 - YAML parsing (imported but used for curriculum files)
- slack-bolt ^1.20.0 - Slack interactive message handlers (`app/socket_server.py`)

**Infrastructure:**
- None detected beyond stdlib

## Configuration

**Environment:**
- Configuration via environment variables (`.env` file exists but not committed)
- Example config: `.env.example` - Template for required env vars
- Custom loader: `environment.py` - Loads `.env` from multiple locations
- See INTEGRATIONS.md for required env vars

**Build:**
- `Dockerfile` - Multi-stage Python 3.11-slim container with Poetry
- `docker-compose.yml` - Development/local testing setup
- `build.sh` - Helper script for Docker builds

**Docker Configuration:**
- Base image: `python:3.11-slim`
- Poetry installed in container with timeout tuning (`POETRY_REQUESTS_TIMEOUT=120`)
- Virtual environments disabled in Poetry (`virtualenvs.create false`)
- State directory: `/app/state` (can be overridden via `STATE_DIR` env var)
- Default port: `8080` (Flask server)

## Platform Requirements

**Development:**
- Python 3.10+ (local development)
- Poetry for dependency isolation
- Docker (for consistent container execution)
- Bash (for shell scripts: `entrypoint.sh`, `cron-runner.sh`)

**Production:**
- Docker container (primary deployment target)
- Cron support (installed in container, see `cron-runner.sh`)
- Network access to:
  - AWS Bedrock API (Claude models)
  - Slack APIs (webhooks or Socket Mode)
- Persistent `/state` directory for deduplication and vote storage

## Script Entry Points

**Docker entrypoint:** `app/entrypoint.sh`
- Supports multiple run modes via `RUN_MODE` env var:
  - `job` (default) - Run `app.main` (single coaching job)
  - `server` - Run Flask server (`app.server`)
  - `cron` - Run cron scheduler (`app/cron-runner.sh`)
  - `socket` - Run Slack Socket Mode server (`app.socket_server`)

**Cron runner:** `app/cron-runner.sh`
- Configurable schedule via `CRON_SCHEDULE` env var (default: `*/10 * * * *`)
- Configurable command via `CRON_CMD` env var (default: `python -m app.main --all`)

---

*Stack analysis: 2026-03-26*
