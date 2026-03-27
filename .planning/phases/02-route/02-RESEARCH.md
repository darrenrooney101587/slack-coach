# Phase 2: Route - Research

**Researched:** 2026-03-27
**Domain:** Slack channel routing — bot token `chat.postMessage`, configurable routing rules, private channel membership
**Confidence:** HIGH (all critical claims verified against official Slack docs and existing codebase)

---

## Summary

Phase 2 has a single job: take the Block Kit blocks list produced by `format_recap()` in Phase 1 and post them to the correct Slack channel. The codebase already has all the posting machinery in `app/main.py`'s `DailyCoach.post_to_slack()` — it calls `https://slack.com/api/chat.postMessage` with a bot token and a `channel` field. Phase 2 does NOT re-implement posting; it extracts a standalone `post_recap_to_slack(blocks, channel_id, token)` function from that existing code and wires it into the `/webhooks/fireflies` route in `server.py`.

Routing is the non-trivial part. The requirements call for configurable rules (RTE-01, RTE-03) without code changes. The correct approach for this codebase is a JSON or YAML config file (already established by the `curriculum_file` pattern in `main.py`) plus env var overrides. A router function reads this config at startup and resolves a channel ID from meeting metadata (title keywords, organizer email, or a catch-all default). The Fireflies transcript already provides `title` and `organizer_email` — both are sufficient for v1 routing rules.

Private channel posting (RTE-02) is not a special code path. The Slack API `chat.postMessage` works identically for public and private channels — the only requirement is that the bot token's app has been added to the private channel. The `not_in_channel` error code is the only signal the code needs to handle gracefully.

**Primary recommendation:** Extract a `post_recap(blocks, channel_id)` function that calls `chat.postMessage` using `SLACK_BOT_TOKEN`, implement a `resolve_channel(transcript)` function driven by a JSON/YAML routing config file, and wire both into the `/webhooks/fireflies` handler in `server.py`. No new dependencies are needed.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.31.0 (pinned) | `chat.postMessage` HTTP call | Already in project; existing `post_to_slack()` uses it |
| json / PyYAML | stdlib / 6.0.0 (pinned) | Parse routing config file | Both already in project; PyYAML for YAML config, json for JSON |
| os | stdlib | Read `SLACK_BOT_TOKEN` and `ROUTING_CONFIG_FILE` env vars | Standard pattern in this codebase |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | ^7.4.0 (dev) | Tests for router and poster | All new code needs tests |
| pytest-mock | ^3.11.1 (dev) | Mock `requests.post` in posting tests | External API boundary |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| raw `requests.post` to `chat.postMessage` | `slack_sdk.WebClient` | `slack_sdk` is not pinned; `requests` already works and is pinned. Use existing pattern. |
| JSON routing config | Environment variable per channel | A config file scales to N rules; individual env vars become unmanageable past 3 channels |
| JSON routing config | YAML routing config | YAML is already in use (`curriculum_file`); either works. YAML is slightly more readable for humans editing routing rules. Recommend YAML for consistency with `curriculum_file`. |

**Installation:** No new dependencies required.

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── server.py        # Wire resolve_channel() + post_recap() into /webhooks/fireflies
├── router.py        # NEW: resolve_channel(transcript) -> channel_id
├── slack.py         # NEW: post_recap(blocks, channel_id, token) -> None
├── fireflies.py     # Unchanged (Phase 1)
├── formatter.py     # Unchanged (Phase 1)
├── main.py          # Unchanged (daily coach jobs)
├── votes.py         # Unchanged
└── socket_server.py # Unchanged
routing.yml          # NEW: routing rules config (or path set via ROUTING_CONFIG_FILE env var)
tests/
├── test_router.py   # NEW: routing resolution unit tests
├── test_slack_post.py  # NEW: post_recap unit tests (mock requests.post)
├── test_fireflies_webhook.py  # Existing — extend with routing+posting integration
└── test_formatter.py  # Existing — unchanged
```

### Pattern 1: Thin Slack Poster Function

**What:** A pure function that takes blocks + channel_id and calls `chat.postMessage`. One responsibility, no routing logic inside.

**When to use:** Always — keeps posting and routing separate so each can be tested independently.

**Example:**

```python
# app/slack.py
import requests

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"


def post_recap(blocks: list, channel_id: str, bot_token: str) -> None:
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel": channel_id,
        "blocks": blocks,
        "text": "Meeting Recap",
    }
    response = requests.post(SLACK_POST_URL, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error')}")
```

### Pattern 2: Config-Driven Router

**What:** A function that loads routing rules from a YAML/JSON config file (path read from env var) and resolves a channel ID from transcript metadata. Falls back to a default channel if no rule matches.

**When to use:** Always — satisfies RTE-01 and RTE-03 without code changes for new rules.

**Config file format (routing.yml):**

```yaml
# routing.yml — configurable without code changes (RTE-03)
default_channel: "C0DEFAULT123"   # Required catch-all

rules:
  - match_field: "organizer_email"
    pattern: "@eng.example.com"
    channel: "C0ENGINEERING1"

  - match_field: "title"
    pattern: "design review"        # case-insensitive substring match
    channel: "C0DESIGNCHAN1"

  - match_field: "organizer_email"
    pattern: "alice@example.com"
    channel: "C0ALICETEAM11"
```

**Router function:**

```python
# app/router.py
import os
import re
import yaml


def load_routing_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def resolve_channel(transcript: dict, config: dict) -> str:
    rules = config.get("rules", [])
    for rule in rules:
        field = rule.get("match_field", "")
        pattern = rule.get("pattern", "")
        channel = rule.get("channel", "")

        value = ""
        if field == "title":
            value = transcript.get("title") or ""
        elif field == "organizer_email":
            value = transcript.get("organizer_email") or ""

        if pattern and value and re.search(pattern, value, re.IGNORECASE):
            return channel

    return config.get("default_channel", "")
```

### Pattern 3: Wire Into server.py Fireflies Route

**What:** Load config once at module level (startup), call `resolve_channel()` and `post_recap()` inside the existing `/webhooks/fireflies` handler after `format_recap()` produces blocks.

**When to use:** Always — the route already exists, Phase 2 only adds the final two steps.

**Example (additions to existing handler):**

```python
# app/server.py additions

import yaml
from router import resolve_channel, load_routing_config
from slack import post_recap

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
ROUTING_CONFIG_FILE = os.environ.get("ROUTING_CONFIG_FILE", "/app/routing.yml")

_routing_config = None

def _get_routing_config():
    global _routing_config
    if _routing_config is None:
        try:
            _routing_config = load_routing_config(ROUTING_CONFIG_FILE)
        except Exception as e:
            app.logger.error(f"Failed to load routing config: {e}")
            _routing_config = {}
    return _routing_config


# In fireflies_webhook() after blocks = format_recap(transcript):
config = _get_routing_config()
channel_id = resolve_channel(transcript, config)

if not channel_id:
    return jsonify({"ok": False, "error": "no_routing_target"}), 500

if not SLACK_BOT_TOKEN:
    return jsonify({"ok": False, "error": "no_bot_token"}), 500

try:
    post_recap(blocks, channel_id, SLACK_BOT_TOKEN)
except RuntimeError as e:
    error_str = str(e)
    if "not_in_channel" in error_str:
        return jsonify({"ok": False, "error": "bot_not_in_channel", "channel": channel_id}), 403
    app.logger.error(f"Slack posting failed: {e}")
    return jsonify({"ok": False, "error": "slack_post_failed"}), 500

return jsonify({"ok": True}), 200
```

### Anti-Patterns to Avoid

- **Returning hardcoded channel IDs in server.py:** Violates RTE-03. Channel IDs belong in the routing config or env vars, not in code.
- **Loading routing config on every request:** Parse config once at startup (module-level lazy load). Reloading a YAML file on every webhook hit adds latency and disk I/O.
- **Silently swallowing `not_in_channel`:** This error means the recap was lost. Return a 403 response so Fireflies can potentially retry or the operator can see the failure.
- **Using channel names instead of channel IDs in config:** The Slack API requires channel IDs (e.g., `C0123456789`) for private channels. Channel names cause `channel_not_found` for private channels. Document this requirement explicitly in `routing.yml` comments.
- **Duplicating post_to_slack logic from main.py:** `DailyCoach.post_to_slack()` is tightly coupled to the daily coach's Block Kit structure (voting buttons, topic header, etc.). The recap poster only needs to send pre-built blocks — extract a new minimal function rather than reusing the existing one.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slack API HTTP client | Custom retry/auth logic | `requests.post` with raise_for_status + json response check | Already the pattern in `main.py`; works correctly |
| YAML config parsing | Custom string parser | `yaml.safe_load` (PyYAML already pinned) | Edge cases in YAML are numerous; safe_load handles them |
| Case-insensitive substring match | Custom string logic | `re.search(pattern, value, re.IGNORECASE)` | stdlib; handles both substring and regex patterns in one call |

**Key insight:** Routing configuration is structurally similar to the existing `curriculum_file` YAML pattern already in `main.py`. Reuse the same approach: env var for path, YAML file for content, load once at startup.

---

## Common Pitfalls

### Pitfall 1: Channel Name vs Channel ID for Private Channels

**What goes wrong:** Routing config contains `#private-channel-name` or `private-channel-name`. Slack API returns `channel_not_found` for private channels addressed by name.

**Why it happens:** Public channels can be referenced by name or ID. Private channels require the encoded ID (starts with `C` for channels, legacy `G` for group DMs).

**How to avoid:** Document clearly in `routing.yml` that all `channel` values must be Slack channel IDs. Add a comment to the config file template. The channel ID is visible in the Slack UI: right-click a channel → "View channel details" → copy the ID at the bottom.

**Warning signs:** `channel_not_found` error for channels that definitely exist.

### Pitfall 2: Bot Not Invited to Private Channel

**What goes wrong:** `chat.postMessage` returns `{"ok": false, "error": "not_in_channel"}` for a correctly-configured private channel ID.

**Why it happens:** Bot tokens cannot post to private channels unless the bot has been explicitly `/invited` to that channel by a member. This is a Slack permission model requirement.

**How to avoid:** This is a deployment/ops step, not a code fix. The code must handle `not_in_channel` gracefully (log it, return informative error). The routing config should only list private channels where the bot has already been invited.

**Warning signs:** Correct channel ID in config, correct token scopes, but `not_in_channel` error.

### Pitfall 3: Routing Config Missing at Startup

**What goes wrong:** `ROUTING_CONFIG_FILE` is not set or points to a nonexistent path. The `/webhooks/fireflies` handler fails on every request with a file-not-found error.

**Why it happens:** Environment variable not set in Docker or deployment config.

**How to avoid:** Use lazy loading with graceful fallback. If config cannot be loaded, log an error and return `{"ok": false, "error": "no_routing_target"}` rather than crashing Flask. Alternatively, support a `DEFAULT_SLACK_CHANNEL_ID` env var as a no-config fallback for simple single-channel deployments.

**Warning signs:** All webhook requests return 500 immediately after deploy.

### Pitfall 4: No Default Channel Causes Silent Drop

**What goes wrong:** A transcript's title and organizer email match no routing rule. `resolve_channel()` returns empty string. The recap is silently discarded with no error.

**Why it happens:** Config file has rules but no `default_channel` entry; router returns `""`.

**How to avoid:** `resolve_channel()` must always return a channel ID or raise/return a sentinel that the caller can detect. The caller must return an error response (not 200) when no channel is resolved.

**Warning signs:** Fireflies webhooks return 200 but no messages appear in Slack.

### Pitfall 5: Routing Config Loaded Inside Request Handler

**What goes wrong:** YAML config is parsed on every webhook request, adding latency and making the app fail on every request if the file is temporarily inaccessible.

**Why it happens:** Config loading placed inside the route function instead of at module level.

**How to avoid:** Use module-level lazy initialization (global + None sentinel). Load once on first request, cache forever. This matches the existing `main.py` pattern for env var loading.

---

## Code Examples

Verified patterns from existing codebase and official sources:

### Existing `chat.postMessage` call (app/main.py — confirmed working)

```python
# Source: app/main.py (existing, verified)
response = requests.post(
    'https://slack.com/api/chat.postMessage',
    headers={
        'Authorization': f'Bearer {self.slack_bot_token}',
        'Content-Type': 'application/json',
    },
    json={
        'channel': self.slack_channel_id,
        'blocks': blocks,
        'text': self.title_prefix,
    }
)
response.raise_for_status()
data = response.json()
if not data.get('ok'):
    raise Exception(f"Slack API error: {data.get('error')}")
```

Phase 2's `post_recap()` function follows this exact pattern, stripping out the daily-coach-specific fields.

### Existing YAML config file pattern (app/main.py — confirmed)

```python
# Source: app/main.py (existing, verified)
self.curriculum_file = os.environ.get('CURRICULUM_FILE', '/app/curriculum.yml')
```

`ROUTING_CONFIG_FILE` follows the same convention: env var overrides path, default is `/app/routing.yml`.

### Slack API error code for private channel not-member (official docs)

```
POST https://slack.com/api/chat.postMessage
Response: {"ok": false, "error": "not_in_channel"}
```

The bot must be explicitly invited to any private channel. This is not fixable in code — it is an ops/setup requirement.

### Fireflies transcript fields available for routing (official docs)

```python
# Available from fetch_transcript() response (app/fireflies.py, verified)
transcript = {
    "title": "Q2 Planning Meeting",           # match_field: "title"
    "organizer_email": "alice@example.com",   # match_field: "organizer_email"
    "participants": ["alice@...", "bob@..."],  # available but not in current fetch query
    "transcript_url": "https://...",
    "summary": {...}
}
```

For v1 routing, `title` and `organizer_email` are sufficient. `participants` requires adding the field to the GraphQL query in `fireflies.py`.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hardcoded `SLACK_CHANNEL_ID_VIEW` / `SLACK_CHANNEL_ID_DATA_ENG` per job | Config-file routing rules with default fallback | N channels without code changes |
| Routing decided at class instantiation time | Routing decided per-request from transcript metadata | Same bot can serve multiple teams |

**Deprecated/outdated:**
- Webhook mode (`SLACK_WEBHOOK_URL`): The daily coach supports both webhook and bot modes, but Phase 2 routing requires a bot token because channel targeting via webhooks is fixed at webhook creation time. Only `SLACK_MODE=bot` is relevant for Phase 2.

---

## Open Questions

1. **Should `organizer_email` be added to the `fetch_transcript` GraphQL query?**
   - What we know: `organizer_email` is a documented field on Fireflies transcript. The current query in `app/fireflies.py` does not fetch it.
   - What's unclear: Whether it is reliably populated (not all meeting integrations may populate it).
   - Recommendation: Add `organizer_email` to the GraphQL query for routing use. If it is absent in a specific transcript, the router falls through to the next rule or default — no error.

2. **Single default channel vs required routing match**
   - What we know: RTE-01 says "routed to specific channels based on configurable rules"; RTE-03 says "without code changes".
   - What's unclear: Whether a catch-all default channel is required or whether "no match = drop" is acceptable.
   - Recommendation: Require `default_channel` in the config; treat absence as a config error at startup. This prevents silent drops.

3. **Config file vs pure env var routing for minimal deployments**
   - What we know: A YAML file is the cleanest multi-rule approach. For a single-channel deployment, a file is overhead.
   - What's unclear: Whether operators will commonly want single-channel (simple) vs multi-channel (complex) deployments.
   - Recommendation: Support both. If `ROUTING_CONFIG_FILE` is unset AND `DEFAULT_SLACK_CHANNEL_ID` env var is set, use that as the channel for all recaps. This gives a zero-config path for simple deployments without special-casing routing logic.

---

## Sources

### Primary (HIGH confidence)

- `app/main.py` (existing, verified) — `chat.postMessage` via `requests.post`, bot token pattern, channel ID field, error check on `data.get('ok')`
- `app/server.py` (existing, verified) — Flask route pattern, abort, jsonify, env var loading
- `app/fireflies.py` (existing, verified) — `fetch_transcript()` response shape; `title`, `transcript_url`, `participants` confirmed
- `https://docs.slack.dev/reference/methods/chat.postMessage` — Required scope `chat:write`, `not_in_channel` error, channel ID requirement for private channels, private channel membership requirement
- `https://docs.fireflies.ai/graphql-api/query/transcript` — `organizer_email`, `title`, `participants`, `meeting_attendees` confirmed as available fields

### Secondary (MEDIUM confidence)

- `https://docs.slack.dev/reference/methods/conversations.members` — Bot can verify own membership via `groups:read` scope; verified via official docs
- `pyproject.toml` (verified) — PyYAML 6.0.0 and requests 2.31.0 already pinned; no new deps needed

### Tertiary (LOW confidence)

- Whether `organizer_email` is reliably populated across all Fireflies calendar integrations — documented field but population depends on calendar type; flag for validation during implementation.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already pinned; `chat.postMessage` pattern copied from existing working code
- Architecture (router + poster split): HIGH — follows same separation-of-concerns already in this codebase (formatter, fetcher, server are distinct)
- Private channel posting: HIGH — `not_in_channel` error code confirmed in official docs; membership requirement confirmed
- Routing config format: HIGH — YAML + env var path follows existing `curriculum_file` pattern exactly
- `organizer_email` field reliability: LOW — field is documented but population depends on Fireflies calendar integration type

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (Slack API is stable; routing config pattern is internal)
