# Slack Coach

## What This Is

A Slack bot that generates and delivers daily coaching tips using Claude/Bedrock, with interactive voting for topic selection. Supports multi-channel, multi-coach deployments via webhook or bot token modes, with file-based state for deduplication and vote tracking. Now expanding to integrate Fireflies.ai meeting recaps into Slack channels.

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

### Active

- [ ] Slack workspace preparation for meeting recaps (dedicated channel, bot membership)
- [ ] Standard Fireflies-to-Slack integration (OAuth connect, default channel, auto-send)
- [ ] Custom webhook workflow for advanced formatting and multi-channel routing
- [ ] Human-in-the-loop review workflow (disable auto-send, manual push after review)
- [ ] Slack Huddle capture support via Fireflies

### Out of Scope

- Real-time meeting transcription — Fireflies handles this externally
- Fireflies account provisioning — assumes Fireflies account exists
- Video recording or playback — only text summaries and action items
- Custom AI summarization — uses Fireflies' built-in AI notes

## Context

- Fireflies.ai is an external meeting transcription and summarization service
- Integration is primarily configuration-driven (Fireflies dashboard + Slack app setup)
- Two integration paths: standard app connect (simple) and custom webhooks (advanced)
- The existing slack-coach codebase already has webhook and bot token patterns that can be extended
- Slack Huddles are short voice calls within Slack — Fireflies can auto-capture these if enabled

## Constraints

- **External Dependency**: Fireflies.ai must be configured separately — this project handles the Slack-side integration
- **Private Channels**: Bot must be explicitly invited to private channels before it can post recaps
- **Webhook Security**: Incoming webhooks from Fireflies need validation to prevent spoofing
- **Auto-Pause Caveat**: Fireflies auto-send only works if enabled in integration settings; manual workflow requires disabling it

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Support both standard and webhook integration paths | Standard is simpler for basic use; webhooks enable custom formatting and multi-channel routing | -- Pending |
| Include human-in-the-loop as explicit workflow | Some teams need to vet AI-generated recaps before sharing publicly | -- Pending |
| Dedicated #meeting-recaps channel | Avoids cluttering existing channels with high-volume recap messages | -- Pending |

---
*Last updated: 2026-03-26 after initialization*
