# Testing Patterns

**Analysis Date:** 2026-03-26

## Test Framework

**Runner:**
- pytest ^7.4.0
- Config: No explicit pytest.ini or [tool.pytest.ini_options] in pyproject.toml; defaults used
- conftest.py at `tests/conftest.py` ensures project root is on sys.path for imports

**Assertion Library:**
- Plain `assert` statements exclusively
- pytest built-in exception testing with `pytest.raises()`

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest tests/test_main.py       # Run specific test file
pytest tests/test_main.py::test_init_raises_without_env  # Run single test
pytest -k "channel_isolation"   # Run tests matching pattern
```

## Test File Organization

**Location:**
- Co-located in `tests/` directory parallel to `app/`
- Test files organized by concern, not by production module:
  - `test_main.py`: Tests DailyCoach class (content generation, Slack posting, initialization)
  - `test_channel_isolation.py`: Tests channel-based state isolation
  - `test_feedback_vote_separation.py`: Tests feedback vs vote file separation
  - `test_channel_dedupe_votes.py`: Tests dedupe state per channel
  - `test_real_world_scenario.py`: End-to-end integration scenario

**Naming:**
- Files: `test_<concern>.py`
- Functions: `test_<behavior>_<condition>()` or `test_<what_it_tests>()`
  - Examples: `test_init_raises_without_env`, `test_complete_channel_isolation`, `test_dedupe_check`

**Structure:**
```
tests/
├── conftest.py                     # pytest config, imports, fixtures
├── test_main.py                    # DailyCoach unit tests
├── test_channel_isolation.py       # Channel isolation integration tests
├── test_feedback_vote_separation.py # Vote type separation tests
├── test_channel_dedupe_votes.py    # Dedupe + vote filtering tests
└── test_real_world_scenario.py     # Multi-job scenario tests
```

## Test Structure

**Suite Organization:**
Flat, function-based structure with no TestCase classes:
```python
def test_init_raises_without_env(monkeypatch, coach_args):
    monkeypatch.delenv("AWS_REGION", raising=False)
    with pytest.raises(ValueError, match="Missing AWS_REGION"):
        DailyCoach(**coach_args)
```

**Patterns:**

*Setup (given):* Fixtures provide setup; monkeypatch for env vars:
```python
@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-v2")
    # ... more setup
```

*Execution (when):* Direct function calls with mocked dependencies:
```python
coach = DailyCoach(**coach_args)
result = coach.generate_content("test topic")
```

*Assertion (then):* Plain asserts with descriptive messages:
```python
assert result['text'] == 'Test Message'
assert result['resource_url'] == 'http://example.com'
```

## Mocking

**Framework:** `unittest.mock` (patch, MagicMock, mock_open) via `pytest-mock` ^3.11.1

**Patterns:**

*External Boundaries (APIs, Files):*
```python
@patch('app.main.boto3.client')
def test_generate_content_success(mock_boto, mock_env, coach_args):
    mock_response = {
        'body': MagicMock(read=lambda: json.dumps({
            'content': [{'text': json.dumps({...})}]
        }).encode('utf-8'))
    }
    mock_boto.return_value.invoke_model.return_value = mock_response
    result = coach.generate_content("test topic")
    assert result['text'] == 'Test Message'
```

*File I/O:*
```python
with patch("os.path.exists", return_value=True), \
     patch("builtins.open", mock_open(read_data=json.dumps({...}))):
    is_dupe = coach.check_dedupe("2026-02-07")
    assert is_dupe is True
```

*HTTP Requests:*
```python
@patch('app.main.requests.post')
def test_post_to_slack_webhook(mock_post, mock_env, coach_args):
    coach.post_to_slack("My message", topic="test")
    args, kwargs = mock_post.call_args
    assert args[0] == "https://hooks.slack.com/..."
```

**What to Mock:**
- AWS Bedrock client (external LLM service)
- HTTP requests (Slack API calls, webhooks)
- File system operations (state directory, dedupe files, votes files)
- Environment variables (via monkeypatch, not patching os.environ)

**What NOT to Mock:**
- Core business logic: DailyCoach methods, votes module functions
- Pure functions: `_get_file_path()`, topic selection logic
- Internal state: Dedupe file structure, vote recording (except when testing external dependencies)

## Fixtures and Factories

**Test Data:**

*Environment Fixture* (`tests/test_main.py` lines 13-19):
```python
@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-v2")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/XXX/YYY/ZZZ")
    monkeypatch.setenv("SLACK_MODE", "webhook")
    monkeypatch.setenv("STATE_DIR", "/tmp/test_state")
```

*Constructor Arguments Fixture* (`tests/test_main.py` lines 21-29):
```python
@pytest.fixture
def coach_args():
    return {
        "job_name": "test_job",
        "topics": ["topic1", "topic2"],
        "channel_id": "C123",
        "role_prompt": "You are a tester.",
        "title_prefix": "Test Coach"
    }
```

**Location:**
- Shared fixtures in `tests/conftest.py`
- Module-specific fixtures in test files (e.g., `mock_env`, `coach_args` in test_main.py)
- No factory functions; dicts used for test data

## Coverage

**Requirements:** Not enforced (no coverage config in pyproject.toml)

**View Coverage:** Not configured

**Target Areas Tested:**
- Initialization and environment validation (test_main.py)
- Core workflows (run flow, dedupe logic, topic selection)
- Edge cases (missing files, multiple vote winners, channel isolation)
- Integration scenarios (multi-job channel isolation, vote filtering)

## Test Types

**Unit Tests:**
- Scope: Single method or function
- Approach: Mock external dependencies (Bedrock, file system, HTTP)
- Examples: `test_init_raises_without_env`, `test_dedupe_check`, `test_get_winning_next_topic_imported`
- Located in: `test_main.py`, individual behaviors tested

**Integration Tests:**
- Scope: Multiple components (DailyCoach + votes module + file system)
- Approach: Use real files (tmp_path fixture) but mock external APIs
- Examples: `test_complete_channel_isolation`, `test_feedback_and_votes_separate_files`, `test_view_runs_then_de_runs_independently`
- Located in: `test_channel_isolation.py`, `test_feedback_vote_separation.py`, `test_channel_dedupe_votes.py`, `test_real_world_scenario.py`

**E2E Tests:**
- Not used. Integration tests sufficient for multi-component scenarios

## Common Patterns

**Async Testing:**
- Not applicable; codebase is synchronous

**Error Testing:**
```python
def test_init_raises_without_env(monkeypatch, coach_args):
    monkeypatch.delenv("AWS_REGION", raising=False)
    with pytest.raises(ValueError, match="Missing AWS_REGION"):
        DailyCoach(**coach_args)
```

**Parametrization:**
- Not used; individual tests for different conditions

**Mocking Run Flow** (`test_main.py` lines 87-103):
```python
@patch('app.main.DailyCoach.post_to_slack')
@patch('app.main.DailyCoach.generate_content')
@patch('app.main.DailyCoach.get_topic')
@patch('app.main.DailyCoach.check_dedupe')
def test_run_flow(mock_dedupe, mock_get_topic, mock_gen, mock_post, mock_env, coach_args):
    mock_dedupe.return_value = False
    mock_get_topic.return_value = "Test Topic"
    mock_gen.return_value = {"text": "Content", "resource_url": "url"}

    coach = DailyCoach(**coach_args)
    with patch.object(coach, 'update_dedupe_state'):
        coach.run()

    mock_get_topic.assert_called_once()
    mock_gen.assert_called_once_with("Test Topic")
    mock_post.assert_called_once()
```

**Temporary Directories:**
- Use pytest's `tmp_path` fixture for isolated file operations
- Example: `test_channel_isolation.py` lines 19, uses `tmp_path` for state files

**JSON Assertions:**
```python
with open(votes_file_view, 'r') as f:
    view_data = json.load(f)
assert view_data['last_message_hash'] == 'hash_view'
```

---

*Testing analysis: 2026-03-26*
