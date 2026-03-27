---
phase: 01-receive-and-format
plan: 02
subsystem: api
tags: [flask, fireflies, hmac, webhook, block-kit, pytest]

requires:
  - phase: 01-01
    provides: "verify_fireflies_signature, fetch_transcript (fireflies.py), format_recap (formatter.py)"
provides:
  - "POST /webhooks/fireflies route in server.py with HMAC verification, event filtering, and Block Kit response"
  - "Integration test suite covering all 8 webhook contract assertions"
affects: [01-03]

tech-stack:
  added: []
  patterns:
    - "request.get_data() called before any body access to read raw bytes once for both HMAC and JSON parsing"
    - "FIREFLIES_WEBHOOK_SECRET falsy check skips HMAC verification, enabling dev/test without secrets"
    - "Tests monkeypatch server module globals (FIREFLIES_WEBHOOK_SECRET, FIREFLIES_API_KEY, fetch_transcript) directly"

key-files:
  created:
    - tests/test_fireflies_webhook.py
  modified:
    - app/server.py
    - tests/conftest.py

key-decisions:
  - "Tests import from server (not app.server) by patching conftest.py to add app/ to sys.path alongside project root"
  - "test_no_signature_verification_when_secret_not_configured mocks fetch_transcript to prevent live HTTP call while still verifying 403 is not returned"

patterns-established:
  - "Webhook route pattern: read raw body once, HMAC check if secret set, parse JSON, validate fields, filter events, fetch external data, validate response, format output"
  - "Test fixture pattern: monkeypatch server module globals for secret/key, patch fetch_transcript in server namespace"

duration: 4min
completed: 2026-03-27
---

# Phase 1 Plan 02: Fireflies Webhook Route Summary

**Flask POST /webhooks/fireflies with HMAC gating, event filtering, GraphQL transcript validation, and Block Kit response — covered by 8 integration tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T02:00:51Z
- **Completed:** 2026-03-27T02:04:51Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `/webhooks/fireflies` route registered with full request lifecycle: HMAC verify, JSON parse, meetingId validation, event type filter, transcript fetch, field validation, Block Kit format
- 8 pytest integration tests covering all contract truths from the plan's `must_haves`
- conftest.py updated to expose `app/` directory on sys.path, enabling bare `from server import app` imports in tests

## Task Commits

1. **Task 1: Add /webhooks/fireflies route to server.py** - `72f896e` (feat)
2. **Task 2: Write integration tests for the fireflies webhook route** - `f6f2857` (feat)

## Files Created/Modified
- `app/server.py` - Added FIREFLIES env vars, imports from fireflies/formatter modules, and the /webhooks/fireflies route function
- `tests/test_fireflies_webhook.py` - 8 integration tests with HMAC helper and monkeypatched fixtures
- `tests/conftest.py` - Added APP_DIR to sys.path so intra-app imports work from test context

## Decisions Made
- Tests import `server` directly (not `app.server`) because server.py uses bare imports internally (`from votes import record_vote`, etc.). Adding `app/` to conftest.py sys.path avoids the mismatch between module names used at test time vs runtime.
- `test_no_signature_verification_when_secret_not_configured` mocks `fetch_transcript` to `lambda mid, key: {}` to prevent a live HTTPS call while still exercising the "no 403 when secret is None" contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated conftest.py to add app/ to sys.path**
- **Found during:** Task 2 (writing tests)
- **Issue:** Existing conftest.py only added project root; `from server import app` would fail because Flask's app.py uses bare module imports that require `app/` to be on the path
- **Fix:** Added `APP_DIR = os.path.join(PROJECT_ROOT, "app")` and inserted it at sys.path[0]
- **Files modified:** tests/conftest.py
- **Verification:** All 8 tests collected and imported correctly
- **Committed in:** f6f2857 (Task 2 commit)

**2. [Rule 1 - Bug] test_no_signature_verification_when_secret_not_configured was missing fetch_transcript mock**
- **Found during:** Task 2 verification (test run)
- **Issue:** Without mocking, the test triggered a live requests.post to api.fireflies.ai which raised HTTPError 500, failing the test for the wrong reason
- **Fix:** Added `monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: {})` so the request path is fully exercised without network I/O
- **Files modified:** tests/test_fireflies_webhook.py
- **Verification:** 8/8 tests pass
- **Committed in:** f6f2857 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correct test isolation. No scope creep.

## Issues Encountered
- None beyond the auto-fixed deviations above.

## User Setup Required
The route requires `FIREFLIES_WEBHOOK_SECRET` and `FIREFLIES_API_KEY` to be set in the deployment environment for live operation. Tests bypass these via monkeypatching. No setup is required to run the test suite.

## Next Phase Readiness
- Route is complete and tested; ready for Phase 1 Plan 03 (end-to-end formatter coverage) and Phase 2 (routing logic)
- The `format_recap` import is in place; formatter tests (01-03) can now exercise the full pipeline via this route

---
*Phase: 01-receive-and-format*
*Completed: 2026-03-27*

## Self-Check: PASSED

- app/server.py: FOUND (fireflies_webhook function at line 102)
- tests/test_fireflies_webhook.py: FOUND
- tests/conftest.py: FOUND (updated)
- 01-02-SUMMARY.md: FOUND
- commit 72f896e: FOUND (Task 1)
- commit f6f2857: FOUND (Task 2)
