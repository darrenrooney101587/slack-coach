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

from environment import load_env

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
    "Lateral joins"
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
        self.state_dir = os.environ.get('STATE_DIR', '/state')
        self.tz = os.environ.get('TZ', 'UTC')
        self.topic_mode = os.environ.get('TOPIC_MODE', 'rotation')
        self.curriculum_file = os.environ.get('CURRICULUM_FILE', '/app/curriculum.yml')

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

    def _get_today_date(self) -> str:
        """Returns today's date in YYYY-MM-DD format based on configured TZ."""
        # Simple implementation using UTC for consistency if TZ handling is complex without pytz
        # If TZ env var is set, we trust system time (assuming container has correct time or we use simple offset)
        # For simplicity and strictly following standard lib as much as possible:
        # If TZ is provided, we can't easily do it without pytz or zoneinfo (Python 3.9+)
        # Python 3.9+ has zoneinfo. Docker image is python 3.11.

        try:
            from zoneinfo import ZoneInfo
            tz_info = ZoneInfo(self.tz)
        except Exception:
            logger.warning(f"Could not load timezone {self.tz}, falling back to UTC")
            tz_info = datetime.timezone.utc

        return datetime.datetime.now(tz_info).strftime('%Y-%m-%d')

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

    def get_topic(self, seed: int) -> str:
        """Selects a topic based on mode and seed."""
        # Retrieve topic
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
        random.seed(seed)
        return random.choice(topics)

    def generate_content(self, topic: str) -> str:
        """Calls Bedrock to generate the content."""
        prompt = f"""You are an expert Postgres database administrator and educator.
Your task is to create a "Daily SQL Coach" tip about the following topic: "{topic}".

Requirements:
1. One-sentence headline.
2. 2-3 actionable bullet points (highest impact first).
3. A SQL snippet (5-15 lines) demonstrating the concept.
4. One "Why this matters:" sentence.
5. Max ~1200 characters total.
6. Do not include generic fluff.
7. Do not propose destructive SQL (DROP/DELETE/TRUNCATE).
8. Be accurate and technical.
9. Format for Slack (you can use *bold*, `code`, ```code blocks```).

Output the message directly. Do not wrap in JSON.
"""

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
            content = response_body['content'][0]['text']
            return content.strip()

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
                    content = response_body['content'][0]['text']
                    return content.strip()
                except Exception as e2:
                    logger.error(f"Retry without custom credentials failed: {e2}")
                    raise

            raise

    def post_to_slack(self, message: str) -> None:
        """Posts the message to Slack."""
        full_message = f"*{self.title_prefix}*\n\n{message}"

        if self.slack_mode == 'webhook':
            response = requests.post(
                self.slack_webhook_url,
                json={'text': full_message}
            )
            response.raise_for_status()

        elif self.slack_mode == 'bot':
            headers = {
                'Authorization': f'Bearer {self.slack_bot_token}',
                'Content-Type': 'application/json'
            }
            payload = {
                'channel': self.slack_channel_id,
                'text': full_message
            }
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
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

            topic = self.get_topic(seed=date_int)
            content = self.generate_content(topic)

            self.post_to_slack(content)

            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            self.update_dedupe_state(today, content_hash)

        except Exception as e:
            logger.error(f"Job failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    coach = SQLCoach()
    coach.run()
