# Coding Conventions

**Analysis Date:** 2026-03-26

## Naming Patterns

**Files:**
- Lowercase with underscores: `main.py`, `server.py`, `votes.py`, `socket_server.py`
- Test files prefixed with `test_`: `test_main.py`, `test_channel_isolation.py`
- Each test module tests a specific concern (e.g., channel isolation, deduplication, separation)

**Functions:**
- Snake_case for all functions: `get_winning_next_topic()`, `record_vote()`, `check_dedupe()`
- Private/internal functions prefixed with underscore: `_get_file_path()`, `_extract_meta_from_action()`
- Methods describing queries use `get_` prefix: `get_topic()`, `get_next_topic_candidates()`
- Methods describing state updates use `update_` prefix: `update_dedupe_state()`
- Boolean-returning methods use `check_` prefix: `check_dedupe()`

**Variables:**
- Snake_case for all variables: `slack_channel_id`, `bedrock_client`, `state_dir`
- Single letter variables only in tight loops or comprehensions
- Descriptive names preferred over abbreviations: `vote_payload` not `vp`, `response_body` not `rb`
- Constants in UPPERCASE: `DEFAULT_TOPICS`, `DATA_ENGINEERING_TOPICS`, `SLACK_SIGNING_SECRET`

**Types:**
- Class names in PascalCase: `DailyCoach`
- Type hints used consistently in function signatures: `def __init__(self, job_name: str, topics: list, channel_id: str, ...)`
- Return type hints included: `def _get_date(self, days_offset: int = 0) -> str:`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.flake8`, `.pylintrc`, `black` config)
- Follows implicit Python conventions: 4-space indentation, max line length ~120 characters
- Imports organized into standard library, third-party, then local imports

**Linting:**
- Pre-commit hooks enabled via `pre-commit` (version ^3.4.0 in pyproject.toml)
- `detect-secrets` integrated for secret detection
- No explicit linter (flake8/pylint/ruff) configured in pyproject.toml

## Import Organization

**Order:**
1. Standard library: `os`, `sys`, `json`, `logging`, `hashlib`, `datetime`, `random`, `time`, `tempfile`, `re`, `hmac`
2. Third-party: `boto3`, `requests`, `PyYAML`, `Flask`, `slack_bolt`, `pytest`
3. Local imports: `from app.main import`, `from app.votes import`, `from environment import`

**Path Aliases:**
- No path aliases configured
- Absolute imports from package root: `from app.main import DailyCoach`
- Relative imports avoided; full module paths used for clarity

**Import Handling:**
- Graceful fallback for optional imports. In `app/main.py` lines 15-21, `get_winning_next_topic` uses try/except to attempt multiple import paths for compatibility:
  ```python
  try:
      from app.votes import get_winning_next_topic
  except ImportError:
      try:
          from votes import get_winning_next_topic
      except ImportError:
          get_winning_next_topic = None
  ```

## Error Handling

**Patterns:**
- Try/except blocks used for I/O and external service calls
- File operations wrapped: `app/main.py` lines 219-225, check_dedupe() handles read failures gracefully
- JSON parsing failures caught and logged: `app/main.py` lines 357-373, generate_content() handles both valid and malformed Bedrock responses
- Exceptions re-raised after logging when recovery needed: `app/main.py` line 405 retry logic
- ValueError raised for initialization failures with descriptive messages: `app/main.py` lines 118-130

**Error Logging:**
- All exceptions logged with context: `logger.error(f"Failed to decode JSON from model response: {e}. Falling back...")`
- Warnings for degradation: `logger.warning(f"Failed to create state directory '{self.state_dir}': {e}. Trying fallback...")`
- Info logs for workflow decisions: `logger.info(f"[{self.job_name}] Message already sent for date: {today}. Skipping.")`

## Logging

**Framework:** Python's standard `logging` module

**Setup Pattern** (`app/main.py` lines 23-28):
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
```

**Patterns:**
- Logger instantiated per module: `logger = logging.getLogger(__name__)`
- Job context included in log messages: `logger.info(f"[{self.job_name}] ...")`
- Log levels used appropriately:
  - INFO: Workflow progress (topics selected, messages posted, state updates)
  - WARNING: Degradation/fallbacks (missing env vars, file creation failures, credential retries)
  - ERROR: Failures requiring attention (Bedrock invocation failures, vote recording failures)
- No structured logging; all messages are formatted strings

## Comments

**When to Comment:**
- Only when explaining non-obvious logic or intent
- Not used to repeat what code does
- Commented-out code deleted, never committed

**JSDoc/TSDoc:**
- Docstrings used for classes and public functions using triple quotes
- Example from `app/votes.py` lines 8-18:
  ```python
  def _get_file_path(state_dir: str, file_type: str, job: str = None, channel: str = None):
      """
      Generate file path for votes or feedback based on job and channel.
      file_type: 'votes' or 'feedback'
      """
  ```
- Functions include docstrings describing purpose, parameters, and return value
- Inline comments rare; code is self-documenting through naming

## Function Design

**Size:**
- Most functions 10-50 lines
- Complex functions broken into smaller units: `check_dedupe()` (39 lines) includes separate logic for channel-based filenames, legacy migration, and file reading
- `generate_content()` is largest (132 lines) because of multi-stage JSON parsing with fallbacks for Bedrock response variability

**Parameters:**
- Minimal parameter count (1-5 typical); avoid parameter bloat
- Complex data passed as dicts for flexibility: `record_vote(payload: dict, state_dir: str)`
- Optional parameters use defaults: `def get_topic(self, date_seed: int, check_votes: bool = True)`

**Return Values:**
- Functions return minimal data: strings, dicts, bools, or None
- `None` returned for "not found" cases: `get_winning_next_topic()` returns None if no votes exist
- Dicts returned for related data: `get_vote_counts()` returns dict with thumbs_up/down counts and images
- No function returns raw objects unless necessary

## Module Design

**Exports:**
- No `__all__` lists used
- Public functions at module level are implicitly exported
- Private functions prefixed with underscore: `_get_file_path()`, `_extract_meta_from_action()`

**Barrel Files:**
- Not used; `app/__init__.py` is empty
- Imports done explicitly from specific modules: `from app.main import DailyCoach`

**Separation of Concerns:**
- `app/main.py`: DailyCoach class - content generation, Slack posting, deduplication
- `app/votes.py`: Vote recording and aggregation - no dependencies on main.py
- `app/server.py`: Flask webhook endpoint for Slack events
- `app/socket_server.py`: Slack Bolt integration for interactive events
- Each module has a single responsibility

---

*Convention analysis: 2026-03-26*
