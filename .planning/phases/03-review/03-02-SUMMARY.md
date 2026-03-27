---
phase: 03-review
plan: 02
subsystem: api
tags: [slack, requests, chat.postMessage, buttons, actions-block]

# Dependency graph
requires:
  - phase: 02-route
    provides: post_recap in app/slack.py — pattern for Slack API calls reused by send_review_dm
provides:
  - send_review_dm(recap_id, blocks, channel_id, reviewer_user_id, bot_token) in app/slack.py
  - DM payload with recap blocks + divider + section + actions block (Approve/Skip buttons)
  - 7 unit tests covering URL, channel target, block presence, button action_ids, recap_id values, error paths
affects: [03-03, server.py review-mode wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "reviewer_user_id passed as channel to chat.postMessage — opens DM automatically without conversations.open"
    - "recap_id carried as button value field so Slack action payloads route back to correct recap"
    - "review_blocks = list(blocks) + [...] — non-destructive block extension preserving original recap structure"

key-files:
  created: []
  modified:
    - app/slack.py
    - tests/test_slack_post.py

key-decisions:
  - "reviewer_user_id used directly as channel — no conversations.open call needed, Slack opens DM implicitly"
  - "recap_id set as value on both buttons so action handler can identify recap without extra state"
  - "RuntimeError message format: 'Slack DM failed: {error}' — distinct from post_recap's 'Slack API error:' for easier debugging"

patterns-established:
  - "Block composition: append review UI blocks to existing recap blocks rather than replacing"
  - "Test assertions: extract all_elements via list comprehension across blocks to check action_ids and values"

# Metrics
duration: 3min
completed: 2026-03-27
tokens_used: ~12k
---

# Phase 3 Plan 02: send_review_dm Summary

**send_review_dm added to app/slack.py — posts recap DM with Approve/Skip action buttons carrying recap_id to reviewer_user_id**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T15:25:38Z
- **Completed:** 2026-03-27T15:28:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `send_review_dm` function in `app/slack.py` builds and posts a DM payload containing recap blocks plus a review actions block
- Actions block has two buttons: Approve (primary) and Skip (danger), both carrying `recap_id` as their value
- 7 unit tests covering URL, channel targeting, block inclusion, button presence, recap_id value propagation, and both error paths
- Full test suite remains at 72 passing (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add send_review_dm to app/slack.py** - `55ddf0f` (feat)
2. **Task 2: Unit tests for send_review_dm** - `269a627` (test)

**Plan metadata:** (this summary commit)

## Files Created/Modified
- `app/slack.py` - Added `send_review_dm` alongside existing `post_recap`
- `tests/test_slack_post.py` - Added 7 new `send_review_dm` tests; imports updated to include `send_review_dm` and added `REVIEWER_USER_ID` constant

## Decisions Made
- reviewer_user_id passed directly as `channel` to `chat.postMessage` — Slack automatically opens a DM when a user ID is used, no `conversations.open` call required
- recap_id set as `value` on both Approve and Skip buttons — action handlers will receive it in the payload without needing additional state lookup
- Error message uses `"Slack DM failed:"` prefix, distinct from `post_recap`'s `"Slack API error:"` — aids debugging when both functions are in use

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `send_review_dm` is ready for `server.py` to call when review mode is active (03-03)
- Function signature matches the `key_links` spec: `send_review_dm(recap_id, blocks, channel_id, reviewer_user_id, bot_token)`
- Approve/Skip button action_ids (`recap_approve`, `recap_skip`) are defined and ready for Slack action handler routing

---
*Phase: 03-review*
*Completed: 2026-03-27*

## Self-Check: PASSED

- app/slack.py: FOUND
- tests/test_slack_post.py: FOUND
- 03-02-SUMMARY.md: FOUND
- Commit 55ddf0f (feat): FOUND
- Commit 269a627 (test): FOUND
