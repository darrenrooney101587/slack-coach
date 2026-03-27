# Roadmap: Slack Coach — Fireflies Integration

## Overview

Three phases deliver the Fireflies-to-Slack middleware pipeline. The first phase stands up the webhook endpoint and produces formatted Slack messages. The second phase routes those messages to the correct channels based on configurable rules. The third phase wraps the pipeline with a human review gate for teams that need to approve recaps before they reach Slack.

## Phases

- [x] **Phase 1: Receive and Format** - Webhook endpoint accepts Fireflies payloads and transforms them into Slack Block Kit messages (completed 2026-03-27)
- [x] **Phase 2: Route** - Formatted recaps are delivered to the correct Slack channels based on configurable routing rules (completed 2026-03-27)
- [ ] **Phase 3: Review** - Manual review mode holds recaps for approval before they reach Slack

## Phase Details

### Phase 1: Receive and Format
**Goal**: Fireflies webhook payloads arrive, are validated, and become ready-to-send Slack messages
**Depends on**: Nothing (first phase)
**Requirements**: HOOK-01, HOOK-02, HOOK-03, FMT-01, FMT-02, FMT-03
**Success Criteria** (what must be TRUE):
  1. A POST to the webhook endpoint with a valid Fireflies payload returns 200 and produces a formatted Block Kit message
  2. A POST with missing required fields (summary, action items, transcript link) is rejected with a non-200 response
  3. A POST with no authorization or a bad signature is rejected before any processing occurs
  4. A payload with optional fields omitted still produces a valid Block Kit message without errors
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Create app/fireflies.py (HMAC verify + GraphQL fetch) and app/formatter.py (pure Block Kit formatter)
- [ ] 01-02-PLAN.md — Register /webhooks/fireflies route in server.py and write integration tests
- [ ] 01-03-PLAN.md — TDD unit tests for format_recap formatter function

### Phase 2: Route
**Goal**: Formatted recaps reach the intended Slack channels without hardcoded channel names
**Depends on**: Phase 1
**Requirements**: RTE-01, RTE-02, RTE-03
**Success Criteria** (what must be TRUE):
  1. A recap is posted to the channel specified by the routing configuration, not a hardcoded default
  2. A recap is successfully posted to a private channel after the bot has been invited to that channel
  3. Routing rules can be changed via config file or environment variable without modifying code
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — TDD for app/router.py (config loading + resolve_channel with all rule cases)
- [ ] 02-02-PLAN.md — Implement app/slack.py (post_recap function) and unit tests
- [ ] 02-03-PLAN.md — Wire router + poster into server.py, add organizer_email to GraphQL query, create routing.yml, extend integration tests

### Phase 3: Review
**Goal**: Teams can hold recaps for human approval before they appear in Slack
**Depends on**: Phase 2
**Requirements**: REV-01, REV-02
**Success Criteria** (what must be TRUE):
  1. When review mode is enabled, an incoming recap is held and does not post to Slack automatically
  2. A reviewer can approve a held recap and it posts to the intended channel
  3. A reviewer can skip a held recap and it is discarded without posting
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — TDD for app/review.py (hold_recap / pop_recap file-backed state)
- [ ] 03-02-PLAN.md — Add send_review_dm to app/slack.py with unit tests
- [ ] 03-03-PLAN.md — Wire review gate into server.py and socket_server.py; integration tests

## Progress

**Execution Order:** 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Receive and Format | 0/3 | Complete    | 2026-03-27 |
| 2. Route | 0/3 | Complete    | 2026-03-27 |
| 3. Review | 0/3 | Not started | - |
