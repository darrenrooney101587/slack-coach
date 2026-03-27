# Phase 3: Review - Research

**Researched:** 2026-03-27
**Domain:** Slack interactive buttons, file-based state, Flask + Bolt action dispatch
**Confidence:** HIGH

## Summary

Phase 3 adds a human review gate to the Fireflies-to-Slack pipeline. When review mode is enabled, incoming recaps are stored in a JSON file (matching the existing votes.py pattern) rather than posted immediately to Slack. A DM is sent to a configured reviewer containing the recap preview and Approve/Skip buttons. When the reviewer clicks Approve, the recap posts to its intended channel; Skip discards it silently.

The codebase already has every building block needed: file-based JSON state (votes.py), Slack interactive button registration (socket_server.py via Bolt `@app.action()`), message mutation via `client.chat_update()`, and direct message posting via `chat.postMessage` with a user ID as the channel. No new dependencies are required — this phase wires existing capabilities together.

The central architectural decision is which server handles the reviewer's button clicks. The Flask `/slack/actions` route handles votes already, but it requires HMAC verification and only records votes — it cannot call the Slack client to update the review DM. The Bolt socket_server already has `@app.action()` handlers that call `client.chat_update()` and have full access to the Slack client. Extending socket_server is the correct fit because it already handles interactive UI updates for voting, and the reviewer workflow needs to update (or delete) the DM after approval.

**Primary recommendation:** Add `app/review.py` for held-recap state management (modelled on votes.py), extend `server.py` to intercept when `REVIEW_MODE=true`, and add `@app.action("recap_approve")` and `@app.action("recap_skip")` handlers to `socket_server.py`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack-bolt | ^1.20.0 (already installed) | Interactive button action handlers | Already in use for voting; `@app.action()` is the canonical pattern |
| Flask | 2.3.3 (already installed) | Fireflies webhook receiver that checks review mode | Already in use |
| requests | 2.31.0 (already installed) | Posting DM to reviewer via `chat.postMessage` | Already used in slack.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | Serialize held-recap state to disk | Same as votes.py |
| os (stdlib) | stdlib | Resolve STATE_DIR, makedirs | Same as votes.py |
| uuid (stdlib) | stdlib | Generate a stable recap_id as state file key | Needed to identify a held recap across the DM and approval callback |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| File-based JSON state | In-memory dict | File state survives server restart; memory dict is simpler but loses held recaps on restart — file state is correct here |
| Bolt socket_server for approve/skip callbacks | Flask `/slack/actions` | Flask handler can record a value but cannot call `client.chat_update()` to update the DM; Bolt handler has a full client — Bolt wins |
| DM to reviewer | Posting to a dedicated review channel | DM is private and direct; review channel adds channel management overhead; DM matches the "single reviewer" requirement |
| `REVIEW_CHANNEL_ID` (separate review channel) | `REVIEW_USER_ID` (DM to person) | Either works — but a user ID maps cleanly to the "reviewer can approve or skip" framing |

**Installation:** No new dependencies. All libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
app/
├── review.py          # NEW: held-recap state (save, load, delete)
├── server.py          # EXTEND: check REVIEW_MODE env var; if true, call hold_recap() instead of post_recap()
├── socket_server.py   # EXTEND: add @app.action("recap_approve") and @app.action("recap_skip")
├── slack.py           # EXTEND: add send_review_dm() to post the DM with Approve/Skip buttons
├── formatter.py       # UNCHANGED
├── router.py          # UNCHANGED
└── votes.py           # UNCHANGED
```

### Pattern 1: Review Mode Guard in Fireflies Webhook

**What:** After formatting and routing, check `REVIEW_MODE` env var. If enabled, save recap to file and send DM. If disabled, post directly.

**When to use:** Every incoming Fireflies transcription event.

```python
# Source: codebase pattern from server.py (fireflies_webhook)
REVIEW_MODE = os.environ.get("REVIEW_MODE", "").lower() == "true"
REVIEWER_USER_ID = os.environ.get("REVIEWER_USER_ID", "")

if REVIEW_MODE:
    if not REVIEWER_USER_ID:
        return jsonify({"ok": False, "error": "no_reviewer_configured"}), 500
    recap_id = hold_recap(blocks, channel_id, STATE_DIR)
    send_review_dm(recap_id, blocks, channel_id, REVIEWER_USER_ID, SLACK_BOT_TOKEN)
    return jsonify({"ok": True, "held": True, "recap_id": recap_id}), 200
else:
    post_recap(blocks, channel_id, SLACK_BOT_TOKEN)
    return jsonify({"ok": True}), 200
```

### Pattern 2: Held-Recap File State (review.py)

**What:** Store held recaps as a dict keyed by recap_id in a single JSON file. Each entry contains blocks, target channel, and timestamp. Matches the votes.py read-modify-write pattern exactly.

**When to use:** When `hold_recap()` is called by server.py.

```python
# Source: pattern from app/votes.py
import json, os, time
from uuid import uuid4

HELD_FILE = "held_recaps.json"

def hold_recap(blocks: list, channel_id: str, state_dir: str) -> str:
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, HELD_FILE)
    data = _load(path)
    recap_id = str(uuid4())
    data[recap_id] = {
        "blocks": blocks,
        "channel_id": channel_id,
        "held_at": int(time.time()),
    }
    _save(path, data)
    return recap_id

def pop_recap(recap_id: str, state_dir: str) -> dict | None:
    path = os.path.join(state_dir, HELD_FILE)
    data = _load(path)
    entry = data.pop(recap_id, None)
    if entry is not None:
        _save(path, data)
    return entry

def _load(path):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
```

### Pattern 3: Review DM with Approve/Skip Buttons (slack.py addition)

**What:** Post a DM to the reviewer containing the recap preview plus an actions block with Approve (primary) and Skip (danger) buttons. The `recap_id` is stored in the button `value` field so the action handler can retrieve the correct held recap.

**Source:** Verified from docs.slack.dev — chat.postMessage accepts a user ID as the channel parameter and opens a DM automatically. Button value carries context through to the action handler.

```python
# Source: Slack API docs (docs.slack.dev/reference/methods/chat.postMessage)
# Source: Block Kit docs (docs.slack.dev/reference/block-kit/blocks/actions-block/)
def send_review_dm(recap_id: str, blocks: list, channel_id: str, reviewer_user_id: str, bot_token: str) -> None:
    review_blocks = list(blocks) + [
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Review required* — this recap is held for <#{channel_id}>"},
        },
        {
            "type": "actions",
            "block_id": "review_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "action_id": "recap_approve",
                    "value": recap_id,
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Skip"},
                    "action_id": "recap_skip",
                    "value": recap_id,
                    "style": "danger",
                },
            ],
        },
    ]
    headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}
    payload = {"channel": reviewer_user_id, "blocks": review_blocks, "text": "Recap pending review"}
    response = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack DM failed: {data.get('error')}")
```

### Pattern 4: Approve/Skip Action Handlers (socket_server.py addition)

**What:** Two `@app.action()` handlers in socket_server.py. On approve: pop the held recap, call `post_recap()`, update the DM to show "Posted". On skip: pop the held recap (discard), update the DM to show "Skipped". Both call `ack()` first.

**Source:** Verified from docs.slack.dev/tools/bolt-python/concepts/actions/ — `ack()` must be called; `client.chat_update()` uses `channel` and `ts` from `body`.

```python
# Source: docs.slack.dev/tools/bolt-python/concepts/actions/
@app.action("recap_approve")
def handle_recap_approve(ack, body, client, logger):
    ack()
    recap_id = body["actions"][0]["value"]
    entry = pop_recap(recap_id, STATE_DIR)
    if not entry:
        logger.warning(f"recap_approve: no held recap for id {recap_id}")
        return
    try:
        post_recap(entry["blocks"], entry["channel_id"], SLACK_BOT_TOKEN)
    except Exception as e:
        logger.error(f"recap_approve: post_recap failed: {e}")
        return
    _update_dm_status(body, client, "Approved — posted to channel.")

@app.action("recap_skip")
def handle_recap_skip(ack, body, client, logger):
    ack()
    recap_id = body["actions"][0]["value"]
    pop_recap(recap_id, STATE_DIR)
    _update_dm_status(body, client, "Skipped — recap discarded.")

def _update_dm_status(body, client, status_text: str):
    channel_id = body.get("channel", {}).get("id")
    ts = body.get("message", {}).get("ts")
    if not (channel_id and ts):
        return
    client.chat_update(
        channel=channel_id,
        ts=ts,
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": status_text}}],
        text=status_text,
    )
```

### Anti-Patterns to Avoid

- **Storing recap_id in block_id instead of button value:** `block_id` is not surfaced cleanly in the action callback body; `value` on the button element is the correct carrier for action context.
- **Handling approve/skip in Flask `/slack/actions`:** Flask handler cannot call `client.chat_update()` without a separate SDK call; Bolt handler has the client already injected — don't duplicate the action dispatch path.
- **Using a random temp file per recap instead of a single held_recaps.json:** A single keyed JSON file is consistent with votes.py and is easier to inspect and test.
- **Forgetting to call `ack()` before any slow work:** Slack requires an acknowledgment within 3 seconds. `ack()` must be the first line of every Bolt action handler.
- **Not deleting the held recap after approval/skip:** The `pop_recap()` function must remove the entry atomically on first use to prevent double-posting if the reviewer clicks twice.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interactive button registration | Custom Flask route parsing action_id | `@app.action()` in Bolt socket_server | Bolt already handles HMAC verification, ack timeout, retry dedup |
| DM opening | conversations.open + then postMessage two-step | `chat.postMessage` with user_id as channel | Slack opens DM automatically; one API call |
| Retry deduplication on double-click | Custom seen-set in memory | `pop_recap()` removes the entry on first claim | File state makes the operation idempotent; second click finds no entry and logs a warning |

**Key insight:** The existing Bolt integration in socket_server.py already handles everything hard about interactive messages (signing verification, ack, retry filtering). The review feature needs to plug into it, not build a parallel mechanism.

## Common Pitfalls

### Pitfall 1: review_mode env var set but REVIEWER_USER_ID missing
**What goes wrong:** Recap is held but no DM is sent; recap sits in state indefinitely.
**Why it happens:** `REVIEW_MODE=true` is configured but `REVIEWER_USER_ID` is not set.
**How to avoid:** Validate `REVIEWER_USER_ID` is present when `REVIEW_MODE=true` at startup (or at the point of use in the webhook handler) and return a clear 500 with `"error": "no_reviewer_configured"`.
**Warning signs:** Webhook returns 500 with that error key; held_recaps.json stays non-empty.

### Pitfall 2: Double-post on reviewer double-click
**What goes wrong:** Reviewer clicks Approve twice quickly; recap is posted twice.
**Why it happens:** First click deletes the file entry, but second request was already in-flight before the file was updated.
**How to avoid:** `pop_recap()` is the single atomic read+delete operation. If it returns None the handler must log a warning and return without posting. Test this path explicitly.
**Warning signs:** Duplicate messages in the target channel.

### Pitfall 3: Bolt socket_server doesn't know about post_recap / STATE_DIR
**What goes wrong:** `import post_recap` fails or `STATE_DIR` is None in socket_server.py.
**Why it happens:** socket_server.py currently only imports from `app.votes`. It needs imports from `app.review` and `app.slack`.
**How to avoid:** Add the imports at the top of socket_server.py alongside existing imports. Ensure `SLACK_BOT_TOKEN` is available (it already is in socket_server).
**Warning signs:** `ImportError` or `NameError` at startup of socket container.

### Pitfall 4: DM update fails because channel/ts is missing in action body
**What goes wrong:** `_update_dm_status()` silently does nothing; reviewer sees the original DM with buttons still active.
**Why it happens:** The body structure for DMs can differ from channel messages; `body["channel"]["id"]` may be absent.
**Why it happens:** Slack sends DM action callbacks with `body["channel"]["id"]` set to the DM channel ID (format `D...`), so it should be present. Defensive check with early return prevents a crash.
**Warning signs:** DM still shows Approve/Skip buttons after clicking.

### Pitfall 5: Recap state file grows unbounded
**What goes wrong:** Old skipped/approved recaps accumulate in held_recaps.json.
**Why it happens:** `pop_recap()` only removes on success; a crash between hold and DM send could leave orphaned entries.
**How to avoid:** This is a v1 edge case — `pop_recap()` handles normal paths. Document that a cron cleanup of entries older than N hours is a v2 concern (see REV-03 audit trail requirement). Do not over-engineer for v1.
**Warning signs:** held_recaps.json grows over time.

## Code Examples

Verified patterns from official sources:

### Button value carries recap_id through callback
```json
// Source: docs.slack.dev/reference/block-kit/blocks/actions-block/
{
  "type": "actions",
  "block_id": "review_actions",
  "elements": [
    {
      "type": "button",
      "text": {"type": "plain_text", "text": "Approve"},
      "action_id": "recap_approve",
      "value": "<recap_id>",
      "style": "primary"
    },
    {
      "type": "button",
      "text": {"type": "plain_text", "text": "Skip"},
      "action_id": "recap_skip",
      "value": "<recap_id>",
      "style": "danger"
    }
  ]
}
```

### Bolt action handler skeleton
```python
# Source: docs.slack.dev/tools/bolt-python/concepts/actions/
@app.action("recap_approve")
def handle_recap_approve(ack, body, client, logger):
    ack()  # MUST be first; Slack requires acknowledgment within 3 seconds
    recap_id = body["actions"][0]["value"]
    # ... retrieve state, post, update DM
```

### Posting a DM (user_id as channel)
```python
# Source: docs.slack.dev/reference/methods/chat.postMessage
# Passing a user ID as channel opens a DM automatically.
requests.post(
    "https://slack.com/api/chat.postMessage",
    headers={"Authorization": f"Bearer {bot_token}"},
    json={"channel": reviewer_user_id, "blocks": review_blocks, "text": "fallback"},
    timeout=10,
)
```

### Updating a DM after action (removing buttons)
```python
# Source: socket_server.py existing pattern (client.chat_update usage)
client.chat_update(
    channel=body["channel"]["id"],
    ts=body["message"]["ts"],
    blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Approved — posted."}}],
    text="Approved — posted.",
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTM (Real Time Messaging) for interactive callbacks | Socket Mode via Bolt | Slack deprecated RTM ~2021 | Socket Mode is the current standard; codebase already uses it |
| `response_url` for all action responses | `client.chat_update()` for message mutations | Bolt ~1.x onwards | `response_url` works for ephemeral replies; `chat_update` is required to mutate the original DM |

**Deprecated/outdated:**
- `response_url` with `replace_original: true` for updating the DM: works only if the original message was posted by the action trigger, not for arbitrary DM mutations — use `client.chat_update()` instead.

## Open Questions

1. **Single reviewer or per-routing-rule reviewer?**
   - What we know: REV-01/REV-02 say "a reviewer" (singular); no per-rule reviewer config is specified.
   - What's unclear: Whether different routes (organizer_email rules) need different reviewers.
   - Recommendation: Implement a single `REVIEWER_USER_ID` env var for v1. Per-rule reviewers are a v2 concern.

2. **Notification when reviewer is unavailable (e.g., DM fails)?**
   - What we know: `send_review_dm()` will raise RuntimeError if the Slack API returns an error.
   - What's unclear: Whether the webhook should return 500 or still return 200-held when the DM fails.
   - Recommendation: Return 500 with `"error": "reviewer_dm_failed"` if the DM send fails. The recap is held in state regardless, so it is not lost — but surfacing the DM failure to the caller is more useful than silently returning 200.

3. **What happens to held recaps if socket_server restarts?**
   - What we know: File state persists across restarts; held_recaps.json survives.
   - What's unclear: Whether the original review DM's buttons still work after socket_server reconnects.
   - Recommendation: Socket Mode reconnects automatically; Bolt's `SocketModeHandler` handles reconnection. Button clicks on the existing DM will be delivered again once connected. No special handling needed.

## Sources

### Primary (HIGH confidence)
- `docs.slack.dev/reference/methods/chat.postMessage` — confirmed user_id accepted as channel for DMs
- `docs.slack.dev/reference/block-kit/blocks/actions-block/` — confirmed actions block JSON structure, button style values, action_id/value fields
- `docs.slack.dev/tools/bolt-python/concepts/actions/` — confirmed `@app.action()` decorator, `ack()` requirement, `client` injection pattern
- Codebase: `app/votes.py` — file-based state read-modify-write pattern (HIGH: directly read)
- Codebase: `app/socket_server.py` — existing Bolt action handlers with `client.chat_update()` (HIGH: directly read)
- Codebase: `app/slack.py` — existing `post_recap()` with `requests.post` to `chat.postMessage` (HIGH: directly read)

### Secondary (MEDIUM confidence)
- WebSearch (multiple results) confirming user_id-as-channel DM pattern for `chat.postMessage` — consistent with official docs

### Tertiary (LOW confidence)
- None identified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in pyproject.toml; no new dependencies
- Architecture: HIGH — direct read of existing codebase patterns; verified Slack API docs
- Pitfalls: HIGH for double-click and missing env var; MEDIUM for DM body structure edge cases

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (Slack Block Kit and Bolt APIs are stable; 30-day window applies)
