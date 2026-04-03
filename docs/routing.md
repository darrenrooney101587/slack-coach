# Routing Configuration

The server reads `routing.yml` at startup and caches it for the lifetime of the process. A server restart is required after any changes to the file.

## File Structure

```yaml
default_channel: "C0123456789"

rules:
  - match_field: "title"
    pattern: "Weekly Standup"
    channel: "C0123456789"

  - match_field: "organizer_email"
    pattern: "alice@example\\.com"
    channels:
      - "U0123456789"
      - "U9876543210"
```

## Fields

### `default_channel`

The Slack channel ID to post to when no rule matches. If omitted and no rule matches, the webhook returns a `500 no_routing_target` error and nothing is posted.

### `rules`

An ordered list of routing rules. Rules are evaluated top to bottom and the first match wins.

Each rule has three keys:

| Key | Required | Description |
|---|---|---|
| `match_field` | Yes | Which transcript field to test — `title` or `organizer_email` |
| `pattern` | Yes | A Python regex pattern tested against the field value (case-insensitive) |
| `channel` | One of these | Single Slack destination ID |
| `channels` | One of these | List of Slack destination IDs |

Use `channel` when routing to a single destination. Use `channels` when the recap should be posted to multiple channels or users simultaneously.

## `match_field` Options

**`title`** — matches against the meeting title as set in the calendar invite or Fireflies.

**`organizer_email`** — matches against the email address of the meeting organizer as reported by Fireflies.

## Channel IDs vs User IDs

All values in `channel` and `channels` must be Slack IDs, not names.

- Channel IDs start with `C` (e.g., `C0123456789`). The bot must be invited to the channel before routing to it. Channel names do not work for private channels and should never be used.
- User IDs start with `U` (e.g., `U0123456789`). Routing to a user ID opens a DM from the bot to that user.

To find a channel or user ID in Slack: right-click the channel or user name, select "View channel details" or "View profile", and copy the ID from the bottom of the modal.

## Regex Patterns

Patterns are evaluated with Python's `re.search` and the `IGNORECASE` flag, so a partial match anywhere in the field value is sufficient.

Common patterns:

```yaml
# Exact phrase match anywhere in the title
pattern: "weekly standup"

# Anchored to start of title
pattern: "^\\[Engineering\\]"

# Match an email domain
pattern: "@example\\.com$"

# Match any of several names
pattern: "alice|bob|carol"
```

### Square Bracket Escaping

Square brackets have special meaning in regex character classes. To match a literal `[` or `]` in a title (for example `[Daily Standup] DINO`), escape them with a double backslash in YAML:

```yaml
pattern: "\\[Daily Standup\\] DINO"
```

A single backslash in YAML (`\[`) is consumed by the YAML parser and the regex receives `[`, which is invalid. Always use `\\[` and `\\]`.

## Example Configuration

```yaml
default_channel: "C0ADL1XCJ76"

rules:
  # Match by title pattern — route to two individual DMs
  - match_field: "title"
    pattern: "\\[Daily Standup\\] DINO"
    channels:
      - "U074ZR6DJKZ"
      - "U0327158VA8"

  # Match 1:1 by title — route to a single DM
  - match_field: "title"
    pattern: "Adrian 1:1"
    channels:
      - "U0327158VA8"

  # Route all meetings from a specific organizer to a channel
  - match_field: "organizer_email"
    pattern: "eng-team@example\\.com"
    channel: "C0987654321"
```

## Caching

The routing config is loaded once when the server starts and held in memory. There is no hot-reload. After editing `routing.yml`, restart the server:

```bash
# Docker
docker compose restart coach-server

# Local dev
# Stop and re-run the flask command
```
