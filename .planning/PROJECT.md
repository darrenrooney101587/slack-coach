# Slack Coach

## What This Is

A Slack bot that delivers daily coaching tips (via Claude/Bedrock) and Fireflies.ai meeting recaps to Slack channels. Supports multi-channel deployments with interactive voting, config-driven recap routing, and optional human-in-the-loop review before posting.

## Core Value

Deliver timely, relevant coaching content and meeting recaps to Slack channels with minimal friction and maximum team visibility.

## Requirements

### Validated

- ✓ Daily coaching tips generated via AWS Bedrock (Claude) — existing
- ✓ Slack posting via webhook and bot token modes — existing
- ✓ Interactive voting (thumbs up/down, next-topic selection) — existing
- ✓ Multi-coach support (Postgres, Data Engineering) to separate channels — existing
- ✓ Deduplication via file-based state (prevents double-posting) — existing
- ✓ Socket Mode server for interactive callbacks without public endpoint — existing
- ✓ Flask server for webhook-based interactive callbacks — existing
- ✓ Cron-based scheduling with configurable schedule — existing
- ✓ Docker multi-mode deployment (job/server/cron/socket) — existing
- ✓ Fireflies webhook receiver with HMAC signature verification — v1.0
- ✓ GraphQL transcript fetching from Fireflies API — v1.0
- ✓ Block Kit formatter for meeting recaps (summary, action items, transcript link) — v1.0
- ✓ Graceful handling of missing optional fields in transcripts — v1.0
- ✓ Config-driven channel routing via YAML rules (title/email match) — v1.0
- ✓ Private channel posting when bot is invited — v1.0
- ✓ Routing configuration manageable without code changes — v1.0
- ✓ Manual review mode holding recaps before posting — v1.0
- ✓ Reviewer approve/skip via Slack DM with interactive buttons — v1.0

### Active

(None yet — planning next milestone)

### Out of Scope

- Real-time meeting transcription — Fireflies handles this externally
- Fireflies account provisioning — assumes Fireflies account exists
- Video recording or playback — only text summaries and action items
- Custom AI summarization — uses Fireflies' built-in AI notes
- Direct Fireflies-to-Slack connection — this project is middleware
- Slack Huddle auto-capture — deferred to v2
- Recap storage/logging — deferred to v2
- Review queue with audit trail — deferred to v2

## Context

Shipped v1.0 with 3,296 LOC Python across 79 tests. Tech stack: Flask, slack-bolt, requests, PyYAML, boto3. Fireflies integration is middleware — receives webhook triggers, fetches transcripts via GraphQL, formats as Block Kit, routes to channels via YAML config. Optional review mode holds recaps for human approval via Slack DM.

Deployment note: `routing.yml` must be explicitly copied into Docker container or mounted — the existing Dockerfile only copies `app/`.

## Constraints

- **External Dependency**: Fireflies.ai must be configured separately — this project handles the Slack-side integration
- **Private Channels**: Bot must be explicitly invited to private channels before it can post recaps
- **Webhook Security**: HMAC SHA-256 signature verification on all incoming Fireflies webhooks
- **Fireflies API**: Webhook body is thin (meetingId only); transcript content requires separate GraphQL fetch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Middleware architecture (not direct Fireflies-to-Slack) | Enables custom formatting, multi-channel routing, and review gate | ✓ Good |
| Two-step fetch (webhook trigger + GraphQL) | Fireflies webhook body only contains meetingId; content requires separate API call | ✓ Good |
| YAML-based routing config | Operators can change routing without code changes; follows existing curriculum_file pattern | ✓ Good |
| File-based JSON state for review hold | Matches existing votes.py pattern; no new infrastructure needed | ✓ Good |
| Bolt action handlers for approve/skip | socket_server.py already has interactive button handling; Flask cannot do chat_update | ✓ Good |
| pop_recap atomic read+delete for idempotency | Prevents double-posting on reviewer double-click | ✓ Good |

---
*Last updated: 2026-03-27 after v1.0 milestone*
