import os
import sys
import json
import hashlib
import logging
import datetime
import random
import boto3
import requests
import tempfile
import time

from environment import load_env

try:
    from votes import get_winning_next_topic
except ImportError:
    # If running from different context, might need to adjust path or define mock
    # Should work if running inside container as designed
    get_winning_next_topic = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_env()
# Constants
DEFAULT_TOPICS = [
    "sargable date predicates",
    "avoiding extract() in WHERE clauses",
    "composite indexes for join+filter",
    "efficient group-by month/year",
    "pg_trgm for LIKE/regex",
    "VACUUM/ANALYZE and planner stats",
    "sort/aggregate spill and work_mem",
    "partial indexes and selective predicates",
    "CTEs vs subqueries performance",
    "Heap Only Tuples (HOT) updates",
    "Index-only scans",
    "BRIN indexes for time-series",
    "JSONB indexing and query performance",
    "EXPLAIN ANALYZE interpretation",
    "Connection pooling importance",
    "Postgres lock monitoring",
    "Autovacuum tuning",
    "Partitioning strategies",
    "Lateral joins",

    # Additional expanded topics
    "multi-column index ordering and selectivity",
    "covering indexes and INCLUDE columns",
    "b-tree vs hash vs gin vs gist index tradeoffs",
    "expression indexes for computed columns",
    "constraint exclusion and partition pruning",
    "parallel query planning and tuning",
    "planner statistics_target and histogram selection",
    "VACUUM FREEZE and bloat mitigation",
    "write amplification and fillfactor",
    "checkpoint tuning and wal settings",
    "replication: logical vs physical",
    "hot standby and read-scaling patterns",
    "materialized views and refresh strategies",
    "prepared statements and plan stability",
    "statement timeouts and resource guards",
    "temp file usage and work_mem diagnostics",
    "background writer and maintenance_work_mem",
    "connection/statement pooling (pgbouncer) modes",
    "monitoring with pg_stat_activity and pg_stat_statements",
    "query parallelism pitfalls (too many workers)",
    "declarative partitioning best practices",
    "brin index tuning for append-only workloads",
    "foreign data wrappers and pushdown limitations",
    "optimizing bulk loads (COPY, WAL settings)",
    "hot updates vs HOT chains and preventing bloat",
    "using EXCLUDE indexes for uniqueness with ranges",
    "optimizing ORDER BY with indexes",
    "reducing locking in high-concurrency updates",
    "effective use of ANALYZE and autoanalyze thresholds",
    "choosing the right data types for storage and speed"
]

class SQLCoach:
    def __init__(self) -> None:
        # Required Env Vars
        self.aws_region = os.environ.get('AWS_REGION')
        self.bedrock_model_id = os.environ.get('BEDROCK_MODEL_ID')
        self.slack_mode = os.environ.get('SLACK_MODE', 'webhook').lower()

        # Access Check
        if not self.aws_region or not self.bedrock_model_id:
            raise ValueError("Missing AWS_REGION or BEDROCK_MODEL_ID")

        if self.slack_mode == 'webhook':
            self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
            if not self.slack_webhook_url:
                raise ValueError("SLACK_WEBHOOK_URL required for webhook mode")
        elif self.slack_mode == 'bot':
            self.slack_bot_token = os.environ.get('SLACK_BOT_TOKEN')
            self.slack_channel_id = os.environ.get('SLACK_CHANNEL_ID')
            if not self.slack_bot_token or not self.slack_channel_id:
                raise ValueError("SLACK_BOT_TOKEN and SLACK_CHANNEL_ID required for bot mode")
        else:
            raise ValueError("Invalid SLACK_MODE. Must be 'webhook' or 'bot'")

        # Optional Env Vars
        self.title_prefix = os.environ.get('TITLE_PREFIX', 'Daily Postgres Coach')
        self.temperature = float(os.environ.get('TEMPERATURE', '0.4'))
        self.max_tokens = int(os.environ.get('MAX_TOKENS', '450'))
        self.dedupe_enabled = os.environ.get('DEDUPE_ENABLED', 'true').lower() == 'true'
        # Short subtitle shown under the header as small grey text; configurable per deployment
        self.title_subtitle = os.environ.get('TITLE_SUBTITLE', 'Concise daily Postgres performance tips and practical examples for this channel.')
        # Default to /app/state which is what docker-compose mounts from HOST_STATE_DIR
        self.state_dir = os.environ.get('STATE_DIR', '/app/state')
        self.tz = os.environ.get('TZ', 'UTC')
        self.topic_mode = os.environ.get('TOPIC_MODE', 'rotation')
        self.curriculum_file = os.environ.get('CURRICULUM_FILE', '/app/curriculum.yml')

        # No accessory image is used anymore; remove SLACK_COACH_IMAGE_URL support.
        # self.slack_coach_image_url = os.environ.get('SLACK_COACH_IMAGE_URL')

        # Ensure state dir is writable; fall back to a tmp directory if not.
        # If neither is writable, disable dedupe to avoid crashing on read-only filesystems.
        try:
            os.makedirs(self.state_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create state directory '{self.state_dir}': {e}. Trying fallback (/tmp).")
            fallback = os.environ.get('STATE_DIR_FALLBACK', os.path.join(tempfile.gettempdir(), 'slack-coach-state'))
            try:
                os.makedirs(fallback, exist_ok=True)
                self.state_dir = fallback
                logger.info(f"Using fallback state dir: {self.state_dir}")
            except Exception as e2:
                logger.error(f"Failed to create fallback state directory '{fallback}': {e2}. Disabling dedupe.")
                self.dedupe_enabled = False

        # Support for explicit AWS credentials via the standard env var names
        # If these are set (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), pass them
        # to boto3 so the Bedrock client will use them. Otherwise boto3 will use
        # its normal credential resolution (env, shared config, instance role, etc.).
        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.environ.get('AWS_SESSION_TOKEN')

        # Initialize Boto3 Client
        client_kwargs = {}
        if self.aws_access_key and self.aws_secret_key:
            client_kwargs['aws_access_key_id'] = self.aws_access_key
            client_kwargs['aws_secret_access_key'] = self.aws_secret_key
            if self.aws_session_token:
                client_kwargs['aws_session_token'] = self.aws_session_token

        # remember whether we attempted to use explicit env-provided AWS creds
        self._used_explicit_aws_creds = bool(client_kwargs)

        self.bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.aws_region,
            **client_kwargs
        )

    def _get_date(self, days_offset: int = 0) -> str:
        """Returns date string in YYYY-MM-DD format with optional day offset."""
        try:
            from zoneinfo import ZoneInfo
            tz_info = ZoneInfo(self.tz)
        except Exception:
            # Only warn once if possible, or just log query
            tz_info = datetime.timezone.utc

        dt = datetime.datetime.now(tz_info) + datetime.timedelta(days=days_offset)
        return dt.strftime('%Y-%m-%d')

    def _get_today_date(self) -> str:
        return self._get_date(0)

    def check_dedupe(self, today: str) -> bool:
        """
        Checks if message was already sent today.
        Returns True if already sent, False otherwise.
        """
        if not self.dedupe_enabled:
            return False

        file_path = os.path.join(self.state_dir, 'last_sent.json')

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if data.get('last_sent_date') == today:
                        logger.info(f"Message already sent for date: {today}. Skipping.")
                        return True
            except Exception as e:
                logger.warning(f"Failed to read lock file: {e}")

        return False

    def update_dedupe_state(self, today: str, content_hash: str) -> None:
        """Updates the last_sent.json file."""
        if not self.dedupe_enabled:
            return

        file_path = os.path.join(self.state_dir, 'last_sent.json')
        data = {
            'last_sent_date': today,
            'last_message_hash': content_hash
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f)
            logger.info("Updated dedupe state.")
        except Exception as e:
            logger.error(f"Failed to update lock file: {e}")

    def get_next_topic_candidates(self, current_topic: str) -> list:
        """Selects 3 random topics excluding the current one."""
        # Retrieve pool of topics (similar to get_topic but we just want the list)
        if self.topic_mode == 'curated' and os.path.exists(self.curriculum_file):
            try:
                import yaml
                with open(self.curriculum_file, 'r') as f:
                    data = yaml.safe_load(f)
                    topics = data.get('topics', DEFAULT_TOPICS)
            except Exception:
                topics = DEFAULT_TOPICS
        else:
            topics = DEFAULT_TOPICS

        # Filter out current
        pool = [t for t in topics if t != current_topic]

        # Select 3 unique
        # We use a random seed based on today + salt to ensure consistent candidates for a re-run on same day
        # but different from topic selection seed
        seed = int(time.time()) # Actually, for candidates, random is fine as long as it's fresh
        # But if we want it deterministic per day, use date.
        # Let's just use random.sample
        count = min(3, len(pool))
        return random.sample(pool, count)

    def get_topic(self, date_seed: int, check_votes: bool = True) -> str:
        """Selects a topic based on votes or random seed."""

        # 1. Check for winning vote from yesterday
        if check_votes and get_winning_next_topic:
            yesterday = self._get_date(days_offset=-1)
            winner = get_winning_next_topic(yesterday, self.state_dir)
            if winner:
                logger.info(f"Using voted topic winner from {yesterday}: {winner}")
                return winner

        # 2. Fallback to standard selection
        # Retrieve topic list
        if self.topic_mode == 'curated' and os.path.exists(self.curriculum_file):
            try:
                import yaml
                with open(self.curriculum_file, 'r') as f:
                    data = yaml.safe_load(f)
                    topics = data.get('topics', DEFAULT_TOPICS)
            except Exception as e:
                logger.warning(f"Failed to load curriculum file: {e}. using defaults.")
                topics = DEFAULT_TOPICS
        else:
            topics = DEFAULT_TOPICS

        # Use deterministic random based on seed
        random.seed(date_seed)
        return random.choice(topics)

    def generate_content(self, topic: str) -> dict:
        """Calls Bedrock to generate the content."""
        # Short-circuit for local testing: if DRY_RUN=1 or SLACK_DRY_RUN=1, return a canned payload
        if os.environ.get('DRY_RUN') == '1' or os.environ.get('SLACK_DRY_RUN') == '1':
            logger.info('DRY_RUN detected: returning canned content without invoking Bedrock')
            return {
                "text": f"*{topic}*\n\n• This is a DRY RUN sample message for topic `{topic}`.\n• No external APIs were called.\n\nExample:\n```sql\n-- Sample SQL snippet\nSELECT 1;\n```\n\nImpact: This is a local test run.",
                "resource_url": "https://www.postgresql.org/docs/current/"
            }

        prompt = f"""You are an expert Postgres database administrator and educator.
Create a professional "Daily SQL Coach" tip about: "{topic}".

Structure for the message body:
*Topic Header*: Brief, professional one-line description of the concept (Bold, no "Topic:" prefix)
*Key Insights*: 2-3 concise, high-impact bullet points using '•' character
*Example*: Clean SQL code snippet (5-15 lines) with inline comments
*Impact*: One clear sentence explaining the business/performance value

Guidelines:
- Start the message body directly with the *Topic Header*
- Be precise and technical, avoid generic statements
- Use professional tone suitable for senior engineers
- Format for Slack: *bold* for headers, `inline code`, ```code blocks```
- Use `code` styling (backticks) for SQL keywords, technical terms, and configuration parameters to highlight them
- Keep total length under 1200 characters
- Never suggest destructive operations (DROP/DELETE/TRUNCATE)
- Focus on practical, immediately applicable knowledge

Output valid JSON with the following schema:
{{
  "text": "The formatted message string as per Structure guidelines",
  "resource_url": "A direct URL to the official PostgreSQL documentation regarding the topic. If specific docs aren't found, link to the general index."
}}
Do not include markdown formatting (like ```json) in the response. Output raw JSON only."""

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        logger.info(f"Invoking Bedrock model: {self.bedrock_model_id} for topic: {topic}")
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                body=json.dumps(payload)
            )

            response_body = json.loads(response['body'].read())
            raw_content = response_body['content'][0]['text'].strip()

            # Attempt to clean potential markdown formatting
            if raw_content.startswith('```json'):
                raw_content = raw_content[7:]
            elif raw_content.startswith('```'):
                raw_content = raw_content[3:]
            if raw_content.endswith('```'):
                raw_content = raw_content[:-3]

            try:
                return json.loads(raw_content.strip())
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from model response. Falling back to raw text.")
                return {
                    "text": raw_content.strip(),
                    "resource_url": "https://www.postgresql.org/docs/current/"
                }

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            # If the failure looks like an invalid/expired custom credential, try once
            # to recreate the client without custom AWS_CLAUDE_* creds and retry.
            err_text = str(e).lower()
            if self._used_explicit_aws_creds and ("unrecognizedclientexception" in err_text or "security token" in err_text or "invalid" in err_text):
                logger.warning("Custom AWS credentials appear invalid; retrying with default boto3 credentials.")
                try:
                    self.bedrock_client = boto3.client(
                        service_name='bedrock-runtime',
                        region_name=self.aws_region
                    )
                    response = self.bedrock_client.invoke_model(
                        modelId=self.bedrock_model_id,
                        body=json.dumps(payload)
                    )
                    response_body = json.loads(response['body'].read())
                    raw_content = response_body['content'][0]['text'].strip()

                    if raw_content.startswith('```json'):
                        raw_content = raw_content[7:]
                    elif raw_content.startswith('```'):
                        raw_content = raw_content[3:]
                    if raw_content.endswith('```'):
                        raw_content = raw_content[:-3]

                    return json.loads(raw_content.strip())

                except Exception as e2:
                    logger.error(f"Retry without custom credentials failed: {e2}")
                    raise

            raise

    def post_to_slack(self, message: str, topic: str = None, message_id: str = None, candidates: list = None, resource_url: str = None) -> None:
        """Posts the message to Slack."""
        full_message = f"*{self.title_prefix}*\n\n{message}"
        logger.info(f"Posting to Slack in mode={self.slack_mode} channel={os.environ.get('SLACK_CHANNEL_ID')}")

        # Ensure we have a message_id to include in metadata
        if not message_id:
            message_id = str(int(time.time() * 1000))

        # Shared metadata for buttons
        meta = json.dumps({'message_id': message_id, 'topic': topic, 'date': self._get_today_date()})

        # Note: This implementation no longer supports uploading a base64 image from an env var.
        # If you want an accessory image include a public URL via SLACK_COACH_IMAGE_URL.
        if self.slack_mode == 'webhook':
            # Build the same blocks payload as bot mode so incoming webhooks render the subtitle
            header_section = {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f"*{self.title_prefix}*"}
            }
            header_subtitle_block = None
            if self.title_subtitle:
                header_subtitle_block = {
                    'type': 'context',
                    'elements': [
                        {'type': 'mrkdwn', 'text': self.title_subtitle}
                    ]
                }

            body_section = {'type': 'section', 'text': {'type': 'mrkdwn', 'text': message}}
            blocks = [header_section]
            if header_subtitle_block:
                blocks.append(header_subtitle_block)
            blocks.extend([{'type': 'divider'}, body_section, {'type': 'divider'}])

            # Append Vote for Next Topic Section (same layout as bot)
            if candidates:
                blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': '*Vote for next topic:*'}})
                for i, cand in enumerate(candidates):
                    cand_meta = json.dumps({
                        'message_id': message_id,
                        'topic': topic,
                        'date': self._get_today_date(),
                        'candidate': cand
                    })
                    blocks.append({
                        'type': 'section',
                        'text': {'type': 'mrkdwn', 'text': f"*{cand}*"},
                        'accessory': {
                            'type': 'button',
                            'text': {'type': 'plain_text', 'text': 'Vote'},
                            'action_id': f'vote_next_topic_{i}',
                            'value': cand_meta
                        }
                    })
                    blocks.append({'type': 'context', 'elements': [{'type': 'plain_text', 'emoji': True, 'text': 'No votes'}]})
                blocks.append({'type': 'divider'})

            # Action buttons
            action_elements = [
                {'type': 'button', 'text': {'type': 'plain_text', 'text': 'Helpful', 'emoji': True}, 'action_id': 'thumbs_up', 'style': 'primary', 'value': meta},
                {'type': 'button', 'text': {'type': 'plain_text', 'text': 'Not Helpful', 'emoji': True}, 'action_id': 'thumbs_down', 'style': 'danger', 'value': meta}
            ]
            if resource_url:
                action_elements.append({'type': 'button', 'text': {'type': 'plain_text', 'text': '📖 Docs', 'emoji': True}, 'url': resource_url})
            blocks.append({'type': 'actions', 'elements': action_elements})

            # Dry-run support: if SLACK_DRY_RUN=1, just log the blocks and return
            if os.environ.get('SLACK_DRY_RUN') == '1':
                logger.info(f"Dry run - blocks payload:\n{json.dumps(blocks, indent=2)}")
                return

            response = requests.post(self.slack_webhook_url, json={'blocks': blocks, 'text': self.title_prefix})
            response.raise_for_status()

        elif self.slack_mode == 'bot':

            headers = {
                'Authorization': f'Bearer {self.slack_bot_token}',
                'Content-Type': 'application/json'
            }

            # Build block kit with buttons (meta already defined above)
            # Button values include metadata so the server can record who voted for which topic/date

            # Header Section
            header_section = {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f"*{self.title_prefix}*"}
            }

            # Optional small subtitle shown below the header (renders as small grey text in Slack)
            header_subtitle_block = None
            if self.title_subtitle:
                header_subtitle_block = {
                    'type': 'context',
                    'elements': [
                        {'type': 'mrkdwn', 'text': self.title_subtitle}
                    ]
                }

            # Body Section
            body_section = {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': message}
            }

            # Build blocks: header, optional subtitle, divider, body...
            blocks = [header_section]
            if header_subtitle_block:
                blocks.append(header_subtitle_block)
            blocks.extend([{'type': 'divider'}, body_section, {'type': 'divider'}])

            # Append Vote for Next Topic Section
            if candidates:
                blocks.append({
                    'type': 'section',
                    'text': {'type': 'mrkdwn', 'text': '*Vote for next topic:*'}
                })

                for i, cand in enumerate(candidates):
                    cand_meta = json.dumps({
                        'message_id': message_id,
                        'topic': topic, # current topic context
                        'date': self._get_today_date(),
                        'candidate': cand
                    })

                    # 1. Candidate Section with Vote Button
                    blocks.append({
                        'type': 'section',
                        'text': {'type': 'mrkdwn', 'text': f"*{cand}*"},
                        'accessory': {
                            'type': 'button',
                            'text': {'type': 'plain_text', 'text': 'Vote'},
                            'action_id': f'vote_next_topic_{i}',
                            'value': cand_meta
                        }
                    })

                    # 2. Context with votes for this candidate (initially empty)
                    blocks.append({
                         'type': 'context',
                         'elements': [
                             {'type': 'plain_text', 'emoji': True, 'text': 'No votes'}
                         ]
                    })

                blocks.append({'type': 'divider'})

            # Additional Actions (Helpful / Not Helpful / Docs)
            action_elements = [
                {
                    'type': 'button',
                    # use emoji shortcodes for arrow up/down
                    'text': {'type': 'plain_text', 'text': 'Helpful   :thumbsup:', 'emoji': True},
                    'action_id': 'thumbs_up',
                    'style': 'primary',
                    'value': meta
                },
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': 'Not Helpful   :thumbsdown:', 'emoji': True},
                    'action_id': 'thumbs_down',
                    'style': 'danger',
                    'value': meta
                }
            ]

            # Add "Read Docs" button if URL is available
            if resource_url:
                action_elements.append({
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': '📖 Docs', 'emoji': True},
                    'url': resource_url
                })

            blocks.append({
                'type': 'actions',
                'elements': action_elements
            })

            payload = {
                'channel': self.slack_channel_id,
                'blocks': blocks,
                'text': self.title_prefix
            }

            # Dry-run support for bot mode
            if os.environ.get('SLACK_DRY_RUN') == '1':
                logger.info(f"Dry run - payload to send to chat.postMessage:\n{json.dumps(payload, indent=2)}")
                return

            # Log payload and perform the post
            logger.info(f"Slack payload: {json.dumps(payload)}")
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers=headers,
                json=payload
            )
            try:
                response.raise_for_status()
            except Exception:
                logger.error(f"HTTP error from Slack: status={response.status_code} body={response.text}")
                raise
            data = response.json()
            logger.info(f"Slack API response: {json.dumps(data)}")
            if not data.get('ok'):
                raise Exception(f"Slack API error: {data.get('error')}")

        logger.info("Successfully posted to Slack.")

    def run(self) -> None:
        try:
            today = self._get_today_date()
            if self.check_dedupe(today):
                sys.exit(0)

            # Generate deterministic seed from date
            # YYYY-MM-DD -> integer
            # remove dashes, convert to int
            date_int = int(today.replace('-', ''))

            topic = self.get_topic(date_seed=date_int)

            # Generate candidates for next run
            candidates = self.get_next_topic_candidates(topic)

            content_data = self.generate_content(topic)
            message_text = content_data.get('text', '')
            resource_url = content_data.get('resource_url')

            self.post_to_slack(message_text, topic=topic, candidates=candidates, resource_url=resource_url)

            content_hash = hashlib.sha256(message_text.encode('utf-8')).hexdigest()
            self.update_dedupe_state(today, content_hash)

        except Exception as e:
            logger.error(f"Job failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    coach = SQLCoach()
    coach.run()
