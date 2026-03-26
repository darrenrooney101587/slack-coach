# Codebase Concerns

**Analysis Date:** 2026-03-26

## Tech Debt

**Brittle Import Fallback in DailyCoach:**
- Issue: `app/main.py` (lines 15-21) uses a fragile multi-level import fallback for `get_winning_next_topic`. If the function is renamed or moved, the silent failure (setting it to `None`) masks the problem.
- Files: `app/main.py`
- Impact: Silent runtime failures; votes feature degrades without warning. The code continues as if votes are unavailable rather than failing loudly.
- Fix approach: Replace with explicit error handling or restructure the module to guarantee the import succeeds. Add a startup check that logs a warning if votes functionality is disabled.

**Repetitive State File Path Construction:**
- Issue: The path construction logic for state files is duplicated across three locations: `check_dedupe()`, `update_dedupe_state()`, and vote functions. Changes to naming convention require updates in multiple places.
- Files: `app/main.py` (lines 197-206, 234-238), `app/votes.py` (lines 8-18)
- Impact: Inconsistency risk; easy to break state isolation when refactoring.
- Fix approach: Extract shared path-building logic into a single utility function in `app/votes.py` and import it in `app/main.py`. Both modules should use the same state file naming logic.

**Duplicate JSON Parsing Logic in Bedrock Response Handling:**
- Issue: Response parsing from Bedrock appears twice with similar code paths (lines 322-373 and 385-399 in `app/main.py`).
- Files: `app/main.py` (lines 322-405)
- Impact: Increases maintenance burden; bug fixes must be applied in two places.
- Fix approach: Extract Bedrock response parsing into a separate method `_parse_bedrock_response()` to avoid duplication.

## Known Bugs

**Potential Data Loss on AWS Credential Fallback:**
- Symptom: If Bedrock invocation fails with explicit AWS credentials, the code recreates the boto3 client and retries (lines 378-403 in `app/main.py`). If the retry succeeds, it returns the result but does NOT update `self.bedrock_client` for subsequent calls.
- Files: `app/main.py` (lines 378-403)
- Trigger: Run with invalid AWS credentials set in environment, then valid credentials in IAM role.
- Workaround: The next invocation uses the original invalid credentials and fails unless the error handling catches it again (unreliable).
- Fix approach: Store the successful client for reuse: add `self.bedrock_client = new_client` after successful retry.

**Vote Button UI Update Only Checks Last Block:**
- Symptom: In `app/socket_server.py` (lines 130-144), when handling `thumbs_up` action, the code iterates through blocks in reverse and breaks after finding the first action block. If the action block structure changes or there are multiple action blocks, the logic may fail silently.
- Files: `app/socket_server.py` (lines 130-144, 187-200)
- Trigger: Message structure with multiple action blocks or nested sections.
- Workaround: None; users see stale button text.
- Fix approach: Ensure all action elements in ALL action blocks are updated, not just the first match found.

**Inconsistent Error Handling in Vote Recording:**
- Symptom: `record_vote()` in `app/votes.py` (lines 38-45) silently catches all exceptions when reading existing vote data. If a JSON file is corrupted, it resets to an empty dict without logging or alerting.
- Files: `app/votes.py` (lines 38-45, 111-117, 152-157)
- Trigger: Corrupted vote JSON file.
- Workaround: Manually delete and recreate the vote file.
- Fix approach: Add specific exception handling with logging for JSON decode errors vs. file I/O errors. Log at WARNING level for data loss scenarios.

## Security Considerations

**Missing Slack Request Verification in Socket Mode:**
- Risk: `app/socket_server.py` does not verify Slack request signatures when running in Socket Mode. The `verify_slack_request()` function in `app/server.py` is not used in the Slack Bolt app.
- Files: `app/socket_server.py` (entire file)
- Current mitigation: None; relies on Slack app token secrecy alone.
- Recommendations: Slack Bolt middleware handles signature verification automatically, but ensure `SLACK_APP_TOKEN` is treated as a secret. Add a check to warn if it's missing or invalid at startup.

**Incomplete Slack Signing Secret Validation:**
- Risk: `app/server.py` (line 17) prints a warning if `SLACK_SIGNING_SECRET` is missing but continues to accept all requests. Any unauthenticated caller can post votes.
- Files: `app/server.py` (lines 16-22)
- Current mitigation: Uses `hmac.compare_digest()` to prevent timing attacks when secret is present, but verification is skipped entirely when secret is absent.
- Recommendations: Require `SLACK_SIGNING_SECRET` to be set at startup; fail early rather than logging a warning. Make verification mandatory.

**AWS Credentials Exposure Risk:**
- Risk: `app/main.py` (lines 155-165) reads AWS credentials from environment variables and constructs `client_kwargs` explicitly. If logging is enabled at DEBUG level, these credentials could appear in logs.
- Files: `app/main.py` (lines 155-165)
- Current mitigation: Credentials are only used to construct the boto3 client; they are not logged. The flag `_used_explicit_aws_creds` (line 166) may appear in error messages.
- Recommendations: Verify that logs never include credential values. Use AWS IAM role when possible instead of explicit credentials. Add a check to warn if explicit AWS credentials are detected in environment.

**Bedrock Model ID Hardcoded in Error Messages:**
- Risk: `app/main.py` (line 321) logs the Bedrock model ID. While not a secret, it reveals infrastructure details in logs.
- Files: `app/main.py` (line 321)
- Current mitigation: Model ID is public configuration, not a secret.
- Recommendations: Acceptable as-is, but ensure logs are not exposed to untrusted parties.

## Performance Bottlenecks

**Vote File Reads Not Cached:**
- Problem: Every call to `get_winning_next_topic()`, `get_vote_counts()`, or `get_poll_details()` reads the entire vote file from disk. If the vote file grows large, this becomes slow.
- Files: `app/votes.py` (lines 103-141, 144-184, 187-236)
- Cause: No in-memory cache; each message action triggers a fresh file read.
- Improvement path: Cache vote file contents with a short TTL (e.g., 10 seconds) within the Socket Mode handler process. Invalidate cache when `record_vote()` is called.

**Blocking Slack API Calls for User Image Fetch:**
- Problem: `_get_user_image()` in `app/socket_server.py` (lines 37-45) makes a synchronous API call to Slack. If the call is slow, the entire action handler is blocked.
- Files: `app/socket_server.py` (lines 37-45, 119-125, 176-182, 235-241)
- Cause: No timeout or async handling; single user image fetch can stall the handler.
- Improvement path: Add a timeout (e.g., 2 seconds) to `users_info()` call. If it fails or times out, gracefully degrade to null image. Consider moving image fetch to background task.

**Bedrock Invoke Timeout Not Set:**
- Problem: `app/main.py` (lines 323-326) invokes Bedrock with no timeout. If the model is overloaded, the request can hang indefinitely.
- Files: `app/main.py` (lines 323-326)
- Cause: boto3 Bedrock client does not have a default timeout.
- Improvement path: Add a timeout parameter to `invoke_model()` call or wrap with `signal.alarm()` / `asyncio.wait_for()`.

## Fragile Areas

**Complex JSON Parsing in Bedrock Response Handler:**
- Files: `app/main.py` (lines 328-373)
- Why fragile: The code attempts to parse JSON from the model response, then handles multiple malformed cases (markdown wrappers, double-encoding, regex extraction). Each case adds complexity and potential for edge cases.
- Safe modification: Add comprehensive unit tests covering: valid JSON, markdown-wrapped JSON, double-encoded JSON, malformed JSON. Test with various Bedrock models.
- Test coverage: Currently test_main.py has basic success case; missing failure cases.

**Message Block Structure Assumptions:**
- Files: `app/socket_server.py` (lines 243-290)
- Why fragile: The code assumes a specific block structure (section with vote button followed by context block). If Slack message format or button layout changes, the block index calculation fails silently.
- Safe modification: Add validation that candidate blocks exist before updating; log warnings if structure doesn't match expectations. Add tests for different message layouts.
- Test coverage: No tests for socket_server.py vote handling.

**Vote File Data Structure Assumptions:**
- Files: `app/votes.py` (lines 119-120, 159-160)
- Why fragile: Code checks `isinstance(entry, dict)` but assumes if it's not a dict, it should be skipped silently. No logging of malformed entries.
- Safe modification: Add logging for unexpected data types. Add validation tests for corrupted vote file contents.
- Test coverage: tests have isolated vote tests but don't test corruption scenarios.

## Scaling Limits

**Single State File Per Job/Channel:**
- Current capacity: Vote file JSON is loaded entirely into memory. For a popular coach with thousands of votes per day, the file could grow to megabytes.
- Limit: At ~1KB per vote entry, 10k votes = 10MB file. Loading this on every poll refresh becomes slow.
- Scaling path: Migrate to a database (SQLite for local, PostgreSQL for cloud). Or implement file rotation: archive old vote files by date.

**No Connection Pooling for Slack API:**
- Current capacity: Each Slack API call in socket_server.py uses a new HTTP connection (via slack-bolt).
- Limit: High-concurrency scenarios with many simultaneous actions could exhaust connection pools.
- Scaling path: slack-bolt handles connection pooling internally; verify it's configured correctly. Monitor concurrent requests.

**Bedrock Model Token Limits:**
- Current capacity: max_tokens=450 (configurable). For large topics or complex prompts, output may be truncated.
- Limit: If message is truncated, user sees incomplete content.
- Scaling path: Monitor truncation by checking if response ends abruptly. Increase max_tokens or implement fallback if truncation detected.

## Dependencies at Risk

**Pinned Dependencies Without Upper Bounds:**
- Risk: `pyproject.toml` pins exact versions (e.g., `requests = "2.31.0"`, `boto3 = "1.34.0"`). No range bounds like `^` or `~` means security updates are not auto-picked up.
- Impact: Known vulnerabilities in pinned versions are not addressed until manual update.
- Migration plan: Add caret constraints (`boto3 = "^1.34.0"`) to allow minor/patch updates while ensuring compatibility. Test with newer versions in CI before upgrading.

**slack-bolt with Permissive Range:**
- Risk: `slack-bolt = "^1.20.0"` allows updates to 2.x. Future major version could break the API.
- Impact: Upgrade to 2.x may require code changes to action handlers.
- Migration plan: Test against slack-bolt 2.0 pre-release. Plan migration strategy when 2.0 is stable.

**No Version Constraints for Flask:**
- Risk: `Flask = "2.3.3"` is pinned but Flask 3.x may have breaking changes.
- Impact: Upgrade path is blocked if Flask 3.x introduces incompatibilities.
- Migration plan: Update to `Flask = "^2.3.3"` and test with 3.0 when available.

## Missing Critical Features

**No Vote Deduplication Logic:**
- Problem: Users can vote for the same candidate multiple times by clicking the button repeatedly. Each click records a separate vote.
- Blocks: Voting fairness; same user can skew poll results.
- Fix approach: In `record_vote()`, check if user has already voted for the same candidate on the same date. Update existing vote instead of appending new one (currently done for thumbs up/down but not for next-topic votes).

**No Audit Trail for State Changes:**
- Problem: Vote files are mutated without a changelog. If a file is corrupted or votes disappear, there's no way to trace what happened.
- Blocks: Debugging; compliance.
- Fix approach: Add a changelog JSON file alongside vote data, logging all mutations with timestamp and user.

**No Dashboard or Analytics:**
- Problem: Vote data is written to JSON but never visualized or analyzed. Users can't see voting trends.
- Blocks: Engagement tracking; content strategy.
- Fix approach: Add an analytics dashboard (e.g., Flask endpoint returning vote summary for a job).

## Test Coverage Gaps

**Socket Mode Action Handlers Not Tested:**
- What's not tested: `handle_thumbs_up()`, `handle_thumbs_down()`, `handle_vote_next_topic()` in `app/socket_server.py`.
- Files: `app/socket_server.py` (lines 91-294)
- Risk: Changes to vote recording or UI update logic could silently break without warning.
- Priority: High - these are critical user-facing flows.

**Bedrock Response Parsing Edge Cases:**
- What's not tested: Malformed JSON from Bedrock, double-encoding, markdown wrappers, regex fallback.
- Files: `app/main.py` (lines 328-373)
- Risk: If Bedrock changes output format, the fallback parsing may fail silently.
- Priority: High - generation is the core feature.

**State File Corruption Handling:**
- What's not tested: Loading a corrupted JSON vote file, missing files, permission errors.
- Files: `app/votes.py`
- Risk: Corruption is silently ignored; users don't know votes are lost.
- Priority: Medium - data loss risk.

**Slack Signing Verification:**
- What's not tested: Verifying that unsigned requests are rejected in `app/server.py`.
- Files: `app/server.py` (lines 20-35)
- Risk: If signature verification is disabled, unauthenticated requests are accepted.
- Priority: Medium - security.

**Timeout Handling for Bedrock:**
- What's not tested: Bedrock invocation timeout or slow response.
- Files: `app/main.py` (lines 323-326)
- Risk: No timeout means indefinite hangs.
- Priority: Medium - availability.

**Import Fallback Behavior:**
- What's not tested: Behavior when `get_winning_next_topic` import fails or is None.
- Files: `app/main.py` (lines 15-21, 262-267)
- Risk: Silent feature degradation.
- Priority: Low - already has a test for availability, but should test actual graceful fallback.

---

*Concerns audit: 2026-03-26*
