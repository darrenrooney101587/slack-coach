# Phase 1: Receive and Format - Research

**Researched:** 2026-03-26
**Domain:** Fireflies webhook receiver + Slack Block Kit formatting in Flask/Python
**Confidence:** MEDIUM (Fireflies payload schema partially verified; action_items type unconfirmed)

---

## Summary

The Fireflies webhook POST body is deliberately thin. It contains only `meetingId`, `eventType`, and optionally `clientReferenceId`. The meeting's actual content — summary, action items, transcript URL — must be fetched in a separate call to the Fireflies GraphQL API (`https://api.fireflies.ai/graphql`) using a Bearer API key. This two-step pattern (receive trigger → fetch content → format → produce) is the required architecture for this phase.

Security follows an x-hub-signature / HMAC SHA-256 model. The existing `app/server.py` already implements the same pattern for Slack's signing secret, so the project already has the correct idiom. A new Flask route (`POST /webhooks/fireflies`) registers in the same Flask app and rejects requests before any processing if signature verification fails.

Formatting uses the existing Block Kit dict-literal style already present in `app/main.py`. No new SDK abstractions are needed; the formatter returns a plain Python list of block dicts that downstream code (Phase 2) can post via the webhook or bot token mechanism.

**Primary recommendation:** Register a new route in `app/server.py`, verify `x-hub-signature` before touching the body, fetch transcript data from the Fireflies GraphQL API, then pass the result to a pure formatter function that returns a Block Kit blocks list. Keep the formatter side-effect-free so it is easily unit-testable.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 2.3.3 (pinned) | HTTP server, route registration | Already in project; existing server.py pattern |
| requests | 2.31.0 (pinned) | GraphQL API call to Fireflies | Already in project; used in main.py for Slack posts |
| hmac + hashlib | stdlib | HMAC SHA-256 signature verification | Already used in server.py for Slack signing secret |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | ^7.4.0 (dev) | Unit tests for formatter and validator | All new code requires tests |
| pytest-mock | ^3.11.1 (dev) | Mock the Fireflies GraphQL call in tests | External API boundary |
| json | stdlib | Parse webhook body, build GraphQL payload | Already used everywhere |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| raw requests for GraphQL | gql / sgqlc | gql is cleaner but adds a dependency; requests is already pinned and sufficient for a single query |
| dict literals for blocks | slack_sdk.models.blocks | slack_sdk classes add no value over dicts for this use case; existing code uses dicts |

**Installation:** No new dependencies required. All needed libraries are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

The new code fits into the existing `app/` layout:

```
app/
├── server.py          # Add /webhooks/fireflies route here
├── fireflies.py       # NEW: Fireflies GraphQL fetch + HMAC verify helper
├── formatter.py       # NEW: Pure function: transcript_data -> Block Kit list
├── main.py            # Unchanged (daily coach jobs)
├── votes.py           # Unchanged
└── socket_server.py   # Unchanged
tests/
├── test_fireflies_webhook.py   # NEW: route + HMAC tests
└── test_formatter.py           # NEW: formatter unit tests
```

### Pattern 1: Thin Webhook, Fetch-on-Trigger

**What:** The webhook POST only hands you an ID. Your handler fetches content immediately before responding, then returns 200.

**When to use:** Always — this is the only flow Fireflies supports.

**Example:**
```python
# app/fireflies.py
import os
import hmac
import hashlib
import requests

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"

TRANSCRIPT_QUERY = """
query Transcript($id: String!) {
  transcript(id: $id) {
    id
    title
    transcript_url
    participants
    summary {
      overview
      action_items
      bullet_gist
    }
  }
}
"""


def verify_fireflies_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def fetch_transcript(meeting_id: str, api_key: str) -> dict:
    response = requests.post(
        FIREFLIES_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"query": TRANSCRIPT_QUERY, "variables": {"id": meeting_id}},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", {}).get("transcript", {})
```

### Pattern 2: Pure Formatter Function

**What:** A function that takes transcript data (a dict) and returns a Block Kit blocks list. No I/O, no side effects. Easy to test with `assert formatter(data) == expected_blocks`.

**When to use:** Always — keep formatting separate from HTTP handling and API calls.

**Example:**
```python
# app/formatter.py

def format_recap(transcript: dict) -> list:
    title = transcript.get("title") or "Meeting Recap"
    transcript_url = transcript.get("transcript_url", "")
    summary = transcript.get("summary") or {}
    overview = summary.get("overview") or summary.get("bullet_gist") or ""
    action_items_raw = summary.get("action_items") or ""

    # action_items may be a string (newline-delimited) or list — handle both
    if isinstance(action_items_raw, list):
        action_items_text = "\n".join(f"- {a}" for a in action_items_raw if a)
    else:
        action_items_text = str(action_items_raw).strip()

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
        {"type": "divider"},
    ]

    if overview:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary*\n{overview[:2900]}"},
        })

    if action_items_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Action Items*\n{action_items_text[:2900]}"},
        })

    blocks.append({"type": "divider"})

    if transcript_url:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<{transcript_url}|View full transcript>"},
        })

    return blocks
```

### Pattern 3: Route Registration in server.py

**What:** Add the new route to the existing Flask app in `server.py`. Read raw body before Flask parses it (required for HMAC).

**When to use:** Always — keeps all HTTP endpoints in one file.

**Example:**
```python
# Addition to app/server.py

FIREFLIES_WEBHOOK_SECRET = os.environ.get("FIREFLIES_WEBHOOK_SECRET")
FIREFLIES_API_KEY = os.environ.get("FIREFLIES_API_KEY")


@app.route("/webhooks/fireflies", methods=["POST"])
def fireflies_webhook():
    raw_body = request.get_data()

    if FIREFLIES_WEBHOOK_SECRET:
        sig = request.headers.get("x-hub-signature", "")
        if not verify_fireflies_signature(FIREFLIES_WEBHOOK_SECRET, raw_body, sig):
            abort(403)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    meeting_id = payload.get("meetingId")
    event_type = payload.get("eventType", "")

    if not meeting_id:
        return jsonify({"ok": False, "error": "missing_meetingId"}), 400

    if event_type != "Transcription completed":
        return jsonify({"ok": True, "skipped": True}), 200

    if not FIREFLIES_API_KEY:
        return jsonify({"ok": False, "error": "no_api_key"}), 500

    transcript = fetch_transcript(meeting_id, FIREFLIES_API_KEY)

    summary = transcript.get("summary") or {}
    if not summary.get("overview") and not summary.get("bullet_gist") and not summary.get("action_items"):
        return jsonify({"ok": False, "error": "missing_required_fields"}), 422

    if not transcript.get("transcript_url"):
        return jsonify({"ok": False, "error": "missing_transcript_url"}), 422

    blocks = format_recap(transcript)
    return jsonify({"ok": True, "blocks": blocks}), 200
```

### Anti-Patterns to Avoid

- **Reading request.data after request.json:** Flask consumes the body stream on first read. Always call `request.get_data()` once before any other body access, especially for HMAC verification.
- **Returning 200 for all errors:** Fireflies may retry on non-200. Return 4xx for validation failures so retries don't loop forever on bad payloads.
- **Blocking on GraphQL in the hot path without timeout:** The `fetch_transcript` call is synchronous. Always pass `timeout=` to `requests.post` to avoid hanging the Flask worker.
- **Building the formatter with side effects:** If `format_recap` calls external APIs or writes files, it cannot be unit-tested without mocks. Keep it pure.
- **Using `==` for signature comparison:** Use `hmac.compare_digest` to prevent timing attacks. This is already the pattern in `server.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC signature verification | Custom byte comparison | `hmac.compare_digest` (stdlib) | Timing-attack resistant by design |
| HTTP to Fireflies GraphQL | urllib manually | `requests.post` (already in project) | Error handling, timeout, raise_for_status already tested |
| Block Kit block construction | XML/template engine | Plain Python dicts | Slack expects JSON; dicts are idiomatic in this codebase |

**Key insight:** The hardest part of this phase is the two-step fetch architecture. Don't try to cache or batch Fireflies API calls in Phase 1 — that is over-engineering for the first phase.

---

## Common Pitfalls

### Pitfall 1: Reading the Body Twice (HMAC + JSON Parse)

**What goes wrong:** `request.get_data()` and `request.json` both read the same stream. If `request.json` is called first, HMAC verification receives an empty byte string and always fails.

**Why it happens:** Flask's request body is a stream, not a replayable buffer (unless `get_data()` is called first, which caches it).

**How to avoid:** Call `raw_body = request.get_data()` at the very top of the handler, then `json.loads(raw_body)` for parsing.

**Warning signs:** HMAC verification always fails even with correct secret configured.

### Pitfall 2: action_items Field Type is Unknown

**What goes wrong:** `summary.action_items` from the Fireflies GraphQL response may be a String (newline-delimited), a list of strings, or null. Calling `.join()` on a string or iterating a null crashes.

**Why it happens:** The Fireflies API docs do not specify the type of `action_items` in the GraphQL schema. Community examples are ambiguous. The field description matches both patterns.

**How to avoid:** Defensive handling — use `isinstance(raw, list)` branch and fall back to `str(raw).strip()` for the non-list case. Treat None/falsy as empty string.

**Warning signs:** `TypeError: 'str' object is not an iterator` or `AttributeError: 'NoneType'` in formatter.

### Pitfall 3: section block text > 3000 characters

**What goes wrong:** Slack rejects Block Kit payloads where any section's `text.text` exceeds 3000 characters. Meeting summaries from Fireflies can be long.

**Why it happens:** Fireflies produces detailed AI summaries. No truncation logic = Slack API error.

**How to avoid:** Truncate `overview` and `action_items_text` to 2900 characters each before inserting into block text. Add a truncation notice if content is cut.

**Warning signs:** Slack API returns `invalid_blocks` error on longer meeting summaries.

### Pitfall 4: Webhook Fires Before Transcript is Ready

**What goes wrong:** Fireflies sends "Transcription completed" but GraphQL query for the transcript returns partial or null summary fields.

**Why it happens:** Race condition between webhook delivery and Fireflies' internal processing pipeline.

**How to avoid:** Accept null summary gracefully in the formatter. Phase 1 should not fail hard on null summary fields — return what is available and mark optional fields as missing rather than erroring.

**Warning signs:** Random 422 errors on valid payloads during integration testing.

### Pitfall 5: Returning 200 for Unrecognized Event Types

**What goes wrong:** Fireflies may send event types other than "Transcription completed" in future. A handler that errors on unknown types would break.

**How to avoid:** Return `200 {"ok": true, "skipped": true}` for unrecognized event types. Only process "Transcription completed".

---

## Code Examples

Verified patterns from existing codebase and official sources:

### HMAC Verification (existing server.py pattern — confirmed working)

```python
# Source: app/server.py (existing, verified)
sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}".encode('utf-8')
my_sig = 'v0=' + hmac.new(SLACK_SIGNING_SECRET.encode('utf-8'), sig_basestring, hashlib.sha256).hexdigest()
slack_signature = req.headers.get('X-Slack-Signature', '')
return hmac.compare_digest(my_sig, slack_signature)
```

Fireflies uses the same HMAC SHA-256 model but without the `v0:timestamp:` prefix — it signs the raw payload directly.

### Existing Block Kit dict pattern (from app/main.py — confirmed)

```python
# Source: app/main.py (existing, verified)
header_section = {
    'type': 'section',
    'text': {'type': 'mrkdwn', 'text': f"*{self.title_prefix}*"}
}
body_section = {'type': 'section', 'text': {'type': 'mrkdwn', 'text': message}}
blocks = [header_section, {'type': 'divider'}, body_section, {'type': 'divider'}]
```

The formatter for Phase 1 follows the same dict-literal style, not SDK wrapper classes.

### Fireflies GraphQL request (MEDIUM confidence — verified against official docs)

```python
# Source: https://docs.fireflies.ai/graphql-api/query/transcript
response = requests.post(
    "https://api.fireflies.ai/graphql",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "query": TRANSCRIPT_QUERY,
        "variables": {"id": meeting_id},
    },
    timeout=10,
)
response.raise_for_status()
transcript = response.json()["data"]["transcript"]
```

### Flask abort pattern (existing server.py — confirmed)

```python
# Source: app/server.py (existing, verified)
if not verify_slack_request(request):
    abort(403)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Custom Fireflies→Slack integration (direct) | Middleware: webhook trigger + GraphQL fetch + format | More control; allows custom Block Kit formatting and routing |
| Flat text Slack messages | Block Kit blocks with header/section/divider | Richer UX; parseable structure for downstream routing |

**Deprecated/outdated:**
- `slack_bolt` for incoming webhooks: slack-bolt is in the project for Slack action callbacks (socket mode / HTTP mode interactive), not for posting or receiving Fireflies webhooks. Do not use slack-bolt for the Fireflies endpoint.

---

## Open Questions

1. **`action_items` field type from Fireflies GraphQL**
   - What we know: Field exists in `summary` object. Community examples show it queried as a scalar.
   - What's unclear: Whether the API returns a String (possibly newline-delimited) or `[String]` list.
   - Recommendation: Implement defensive dual-path handling (`isinstance(v, list)` check). Integration test against real Fireflies API or review actual response in developer dashboard to confirm.

2. **x-hub-signature header exact format**
   - What we know: Fireflies sends `x-hub-signature` with HMAC SHA-256 of the payload using a configured secret.
   - What's unclear: Whether the value is a raw hex digest or prefixed (e.g., `sha256=<hex>`). Fireflies docs show the raw hex pattern; GitHub uses `sha256=` prefix. Replit demo link referenced in docs was not publicly accessible.
   - Recommendation: Implement without prefix assumption first. If verification always fails during integration testing, add a strip of any `sha256=` prefix.

3. **Required fields for Phase 1 validation**
   - The success criteria say "missing required fields (summary, action items, transcript link) is rejected". However, Fireflies webhook bodies never contain these — they must be fetched via GraphQL.
   - Recommendation: Validate that the GraphQL response contains at least one of `summary.overview`, `summary.bullet_gist`, or `summary.action_items` (non-empty), and that `transcript_url` is present. Reject (422) only when the fetched data has none of those.

---

## Sources

### Primary (HIGH confidence)

- `app/server.py` — existing HMAC verify pattern, Flask route/abort pattern, `request.get_data()` usage
- `app/main.py` — existing Block Kit dict-literal style confirmed
- `https://docs.fireflies.ai/graphql-api/webhooks` — webhook payload schema: meetingId, eventType, clientReferenceId; x-hub-signature / HMAC SHA-256 security model
- `https://docs.fireflies.ai/graphql-api/query/transcript` — GraphQL transcript query fields: title, transcript_url, participants, summary.overview, summary.action_items, summary.bullet_gist
- `https://docs.slack.dev/reference/block-kit/blocks/section-block/` — section block max 3000 chars for text field

### Secondary (MEDIUM confidence)

- `https://docs.slack.dev/block-kit/` — Block Kit overview, 50-block-per-message limit, available block types
- WebSearch: HMAC SHA-256 `hmac.compare_digest` timing-safe comparison for webhook verification

### Tertiary (LOW confidence)

- `action_items` field type (String vs list): Inferred from multiple community integration examples; not explicitly typed in official schema. Flag for validation during implementation.
- `x-hub-signature` prefix format: Confirmed as raw SHA-256 hex from docs page, but exact format (with/without prefix) not shown in a verifiable code example.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already in `pyproject.toml`; no new deps needed
- Architecture (two-step fetch pattern): HIGH — confirmed by official Fireflies webhook docs showing thin payload
- Block Kit formatting: HIGH — existing code in `app/main.py` demonstrates the exact dict style; section limit verified from official docs
- Fireflies GraphQL fetch: MEDIUM — fields confirmed from official transcript query docs; request pattern from official docs
- `action_items` type: LOW — not explicitly specified in Fireflies schema docs; must be handled defensively

**Research date:** 2026-03-26
**Valid until:** 2026-04-25 (Fireflies API changes infrequently; Slack Block Kit is stable)
