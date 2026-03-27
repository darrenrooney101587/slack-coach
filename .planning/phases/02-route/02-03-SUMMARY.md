---
phase: 02-route
plan: "03"
subsystem: api
tags: [flask, routing, slack, webhook, pytest, monkeypatch]

requires:
  - phase: 02-route
    plan: "01"
    provides: "app/router.py: resolve_channel and load_routing_config pure functions"
  - phase: 02-route
    plan: "02"
    provides: "app/slack.py: post_recap(blocks, channel_id, bot_token)"

provides:
  - "app/fireflies.py: organizer_email field added to GraphQL query"
  - "app/server.py: /webhooks/fireflies handler resolves channel via routing config and posts to Slack"
  - "routing.yml: deployable example config template with default_channel and two sample rules"
  - "tests/test_fireflies_webhook.py: 12 tests covering full routing+posting pipeline and all error paths"

affects:
  - 03-deploy (server.py is the deployed endpoint; routing.yml is operator config)

tech-stack:
  added: []
  patterns:
    - "Lazy singleton: _routing_config global loaded once via _get_routing_config() on first request"
    - "Monkeypatching module-level names: server.post_recap, server._get_routing_config, server.SLACK_BOT_TOKEN patched in tests to replace references handler uses"
    - "Error-code protocol: no_routing_target/no_bot_token/bot_not_in_channel as distinct 500/403 response error strings"

key-files:
  created:
    - routing.yml
  modified:
    - app/fireflies.py
    - app/server.py
    - tests/test_fireflies_webhook.py

key-decisions:
  - "organizer_email added to GraphQL query so transcript dict carries email for routing rules without extra fetch"
  - "ROUTING_CONFIG_FILE env var defaults to /app/routing.yml (Docker path) to match container layout"
  - "_routing_config loaded lazily as global singleton — avoids file I/O on every request while remaining monkeypatchable in tests"
  - "post_recap monkeypatched at server.post_recap (module-level reference) not slack.post_recap — server.py imports at module level so that reference is what the handler calls"

patterns-established:
  - "Pattern: module-level import + singleton loader; monkeypatch server.<name> in tests, not the source module"
  - "Pattern: distinct error codes per failure mode (no_routing_target, no_bot_token, bot_not_in_channel) for operator debuggability"

duration: 5min
completed: 2026-03-27
---

# Phase 2 Plan 03: Server Wire-Up Summary

**Webhook handler now resolves Slack channel via YAML routing config and posts Block Kit recap blocks, with 12 integration tests covering success and all error paths**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T14:23:41Z
- **Completed:** 2026-03-27T14:28:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `organizer_email` to the Fireflies GraphQL query so transcripts carry organizer email for email-based routing rules
- Updated `/webhooks/fireflies` in server.py to resolve channel via `_get_routing_config()` + `resolve_channel()` then post blocks via `post_recap()`
- Created `routing.yml` template with default_channel and two example rules (organizer_email and title match)
- Extended test_fireflies_webhook.py from 8 to 12 tests: updated existing success test and added 4 new tests covering the full pipeline and all error paths

## Task Commits

Each task was committed atomically:

1. **Task 1: Add organizer_email to GraphQL query and create routing.yml** - `effe66d` (feat)
2. **Task 2: Wire routing and posting into server.py and extend integration tests** - `15a4d73` (feat)

## Files Created/Modified

- `app/fireflies.py` - Added organizer_email field to GraphQL transcript query
- `routing.yml` - Example routing config template with default_channel and two sample rules
- `app/server.py` - Imports router+slack; adds SLACK_BOT_TOKEN/ROUTING_CONFIG_FILE constants; _get_routing_config singleton; updated handler to resolve+post
- `tests/test_fireflies_webhook.py` - Added organizer_email to FULL_TRANSCRIPT; updated existing success test; added 4 new integration tests

## Decisions Made

- `organizer_email` added directly to GraphQL query rather than fetched separately — transcript dict is the canonical data carrier for routing
- `ROUTING_CONFIG_FILE` defaults to `/app/routing.yml` to match Docker working directory; operators override via env var
- `_routing_config` lazy singleton mirrors the `curriculum_file` pattern in main.py — single load, restartable, monkeypatchable
- Tests monkeypatch `server.post_recap` (not `slack.post_recap`) because server.py binds the name at import time

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

To deploy routing to real channels:
- Replace channel IDs in `routing.yml` with actual Slack channel IDs (not names)
- Set `ROUTING_CONFIG_FILE` env var to the config file path inside the container
- Set `SLACK_BOT_TOKEN` env var to a bot token with `chat:write` scope
- Invite the bot to each private channel it needs to post to

## Next Phase Readiness

- Phase 2 complete: recaps now route to Slack channels determined by YAML config
- All 55 tests pass
- server.py handler is production-ready; routing.yml template is ready for operator customization
- Phase 3 (deploy) can proceed immediately

---
*Phase: 02-route*
*Completed: 2026-03-27*

## Self-Check: PASSED

- FOUND: app/fireflies.py
- FOUND: routing.yml
- FOUND: app/server.py
- FOUND: tests/test_fireflies_webhook.py
- FOUND: .planning/phases/02-route/02-03-SUMMARY.md
- FOUND: commit effe66d
- FOUND: commit 15a4d73
