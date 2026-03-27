---
phase: 03-review
plan: 03
subsystem: api
tags: [review-mode, webhook, bolt-actions, integration-tests, unit-tests]

requires:
  - phase: 03-review
    plan: 01
    provides: hold_recap and pop_recap in app/review.py
  - phase: 03-review
    plan: 02
    provides: send_review_dm in app/slack.py

provides:
  - REVIEW_MODE guard in fireflies_webhook that holds recaps when active
  - recap_approve Bolt handler that pops recap and posts to channel
  - recap_skip Bolt handler that discards held recap
  - 4 integration tests covering all review-mode webhook paths
  - 3 unit tests covering all Bolt handler behaviors

affects:
  - app/server.py
  - app/socket_server.py
  - tests/test_fireflies_webhook.py
  - tests/test_socket_server_review.py

tech-stack:
  added: []
  patterns:
    - "monkeypatch.setattr(server, 'REVIEW_MODE', True) for per-test flag control (auto-restored)"
    - "Patch slack_bolt.App.__init__ to set token_verification_enabled=False before importing socket_server in tests"
    - "_update_dm_status helper centralizes chat_update call for both approve and skip handlers"

key-files:
  created:
    - tests/test_socket_server_review.py
  modified:
    - app/server.py
    - app/socket_server.py
    - tests/test_fireflies_webhook.py

key-decisions:
  - "monkeypatch used for REVIEW_MODE per-test state — auto-restores after each test, no teardown needed"
  - "Bolt App token_verification_enabled patched at slack_bolt.App.__init__ level rather than changing production code"
  - "sys.modules cleanup only removes app.socket_server and socket_server keys (not the test module itself) to avoid collection errors"

duration: 46min
completed: 2026-03-27
tokens_used: ~18k
---

# Phase 3 Plan 03: Review Gate Wiring Summary

**Review gate wired into server.py and socket_server.py — REVIEW_MODE holds recaps and sends DM; recap_approve posts to channel; recap_skip discards without posting; 79 tests passing**

## Performance

- **Duration:** 46 min
- **Started:** 2026-03-27T15:34:52Z
- **Completed:** 2026-03-27T16:20:49Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `REVIEW_MODE` and `REVIEWER_USER_ID` env var reads added to `server.py`; `hold_recap` and `send_review_dm` imported
- `fireflies_webhook` now branches on `REVIEW_MODE`: holds recap and sends DM when true; posts directly when false
- `recap_approve` and `recap_skip` Bolt action handlers registered in `socket_server.py` with `_update_dm_status` helper
- 4 integration tests cover: holds recap and returns `{held: true}`, missing reviewer returns 500, DM failure returns 500, false mode posts directly
- 3 unit tests cover: approve posts and updates DM, skip discards and updates DM, double-approve is idempotent
- Full test suite: 79 tests passing (72 prior + 4 webhook review mode + 3 handler unit tests)

## Task Commits

1. **Task 1: Add review gate to server.py and action handlers to socket_server.py** — `be49a97` (feat)
2. **Task 2: Integration tests for review mode webhook behavior** — `c0a96d0` (test)
3. **Task 3: Unit tests for recap_approve and recap_skip Bolt handlers** — `259ac84` (test)

## Files Created/Modified

- `app/server.py` — Added REVIEW_MODE guard, hold_recap and send_review_dm imports and calls
- `app/socket_server.py` — Added pop_recap and post_recap imports, _update_dm_status helper, recap_approve and recap_skip handlers
- `tests/test_fireflies_webhook.py` — Added 4 review mode integration tests using monkeypatch pattern
- `tests/test_socket_server_review.py` — Created with 3 unit tests for Bolt handlers

## Decisions Made

- `monkeypatch` used for per-test `REVIEW_MODE` flag control — pytest auto-restores after each test, eliminating manual teardown
- Bolt App token_verification_enabled patched at the `slack_bolt.App.__init__` level before import — avoids live auth.test calls without modifying production code
- `sys.modules` cleanup in test file scoped precisely to `app.socket_server` and `socket_server` keys only — avoids a `KeyError` caused by deleting the test module's own entry during pytest collection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sys.modules deletion caused KeyError during pytest collection**
- **Found during:** Task 3
- **Issue:** Initial implementation deleted all sys.modules keys containing "socket_server", which included `test_socket_server_review` during the module's own collection phase
- **Fix:** Scoped deletion to exactly `("app.socket_server", "socket_server")` keys only
- **Files modified:** `tests/test_socket_server_review.py`
- **Commit:** `259ac84`

## Issues Encountered

None beyond the pytest collection edge case fixed inline above.

## User Setup Required

- Set `REVIEW_MODE=true` and `REVIEWER_USER_ID=<slack-user-id>` in the deployment environment to activate review mode
- Set `REVIEW_MODE=false` or leave unset to preserve the existing direct-post behavior

## Next Phase Readiness

Phase 3 is complete. All three plans executed:
- 03-01: file-backed held_recap state layer
- 03-02: send_review_dm with approve/skip buttons
- 03-03: review gate wired into webhook and Bolt handlers registered

The review gate is fully operational end-to-end.

---
*Phase: 03-review*
*Completed: 2026-03-27*

## Self-Check: PASSED

- app/server.py: FOUND
- app/socket_server.py: FOUND
- tests/test_fireflies_webhook.py: FOUND
- tests/test_socket_server_review.py: FOUND
- 03-03-SUMMARY.md: FOUND
- Commit be49a97 (feat - task 1): FOUND
- Commit c0a96d0 (test - task 2): FOUND
- Commit 259ac84 (test - task 3): FOUND
