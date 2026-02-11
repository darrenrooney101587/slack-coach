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
    get_winning_next_topic = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_env()
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

DATA_ENGINEERING_TOPICS = [
    "Parquet vs ORC vs Avro storage formats",
    "Data Lake vs Data Warehouse vs Lakehouse",
    "Idempotency in data pipelines",
    "SCD Type 1 vs Type 2 implementations",
    "Partitioning strategies in Spark/Iceberg",
    "Airflow DAG best practices and anti-patterns",
    "Checkpointing and state management in streaming",
    "Backfilling strategies for historical data",
    "Data Quality checks (Great Expectations/dbt tests)",
    "Data Lineage and impact analysis",
    "Columnar vs Row-oriented storage benefits",
    "MapReduce paradigm and shuffle operations",
    "Serializability and isolation levels in distributed systems",
    "CAP theorem trade-offs involved in data systems",
    "Modern Data Stack tool selection (dbt, Snowflake, etc)",
    "Schema evolution and backward compatibility",
    "Z-ordering and data skipping optimization",
    "Compaction and small file problems"
]

class DailyCoach:
    def __init__(self, job_name: str, topics: list, channel_id: str, role_prompt: str, title_prefix: str) -> None:
        self.job_name = job_name
        self.topics = topics
        self.slack_channel_id = channel_id
        self.role_prompt = role_prompt
        self.title_prefix = title_prefix

        self.aws_region = os.environ.get('AWS_REGION')
        self.bedrock_model_id = os.environ.get('BEDROCK_MODEL_ID')
        self.slack_mode = os.environ.get('SLACK_MODE', 'webhook').lower()

        if not self.aws_region or not self.bedrock_model_id:
            raise ValueError("Missing AWS_REGION or BEDROCK_MODEL_ID")

        if self.slack_mode == 'webhook':
            self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
            if not self.slack_webhook_url:
                raise ValueError("SLACK_WEBHOOK_URL required for webhook mode")
        elif self.slack_mode == 'bot':
            self.slack_bot_token = os.environ.get('SLACK_BOT_TOKEN')
            if not self.slack_bot_token or not self.slack_channel_id:
                raise ValueError("SLACK_BOT_TOKEN and valid Channel ID required for bot mode")
        else:
            raise ValueError("Invalid SLACK_MODE. Must be 'webhook' or 'bot'")

        self.temperature = float(os.environ.get('TEMPERATURE', '0.4'))
        self.max_tokens = int(os.environ.get('MAX_TOKENS', '450'))
        self.dedupe_enabled = os.environ.get('DEDUPE_ENABLED', 'true').lower() == 'true'
        self.title_subtitle = os.environ.get('TITLE_SUBTITLE', 'Concise daily performance tips and practical examples.')
        self.state_dir = os.environ.get('STATE_DIR', '/app/state')
        self.tz = os.environ.get('TZ', 'UTC')
        self.topic_mode = os.environ.get('TOPIC_MODE', 'rotation')
        self.curriculum_file = os.environ.get('CURRICULUM_FILE', '/app/curriculum.yml')

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


        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.environ.get('AWS_SESSION_TOKEN')

        client_kwargs = {}
        if self.aws_access_key and self.aws_secret_key:
            client_kwargs['aws_access_key_id'] = self.aws_access_key
            client_kwargs['aws_secret_access_key'] = self.aws_secret_key
            if self.aws_session_token:
                client_kwargs['aws_session_token'] = self.aws_session_token

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

        channel_suffix = self.slack_channel_id or ''
        if channel_suffix:
            file_path = os.path.join(self.state_dir, f'last_sent_{self.job_name}_{channel_suffix}.json')
        else:
            file_path = os.path.join(self.state_dir, f'last_sent_{self.job_name}.json')

        legacy = os.path.join(self.state_dir, f'last_sent_{self.job_name}.json')
        if not channel_suffix:
            if os.path.exists(legacy):
                file_path = legacy
                logger.info(f"Using legacy dedupe file: {file_path}")
        else:
            if not os.path.exists(file_path) and os.path.exists(legacy) and os.environ.get('MIGRATE_LEGACY_DEDUPE') == '1':
                try:
                    with open(legacy, 'r') as src, open(file_path, 'w') as dst:
                        dst.write(src.read())
                    logger.info(f"Migrated legacy dedupe {legacy} -> {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to migrate legacy dedupe file: {e}")

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if data.get('last_sent_date') == today:
                        logger.info(f"[{self.job_name}] Message already sent for date: {today}. Skipping.")
                        return True
            except Exception as e:
                logger.warning(f"Failed to read lock file: {e}")

        return False

    def update_dedupe_state(self, today: str, content_hash: str) -> None:
        """Updates the last_sent_{job}.json file."""
        if not self.dedupe_enabled:
            return

        channel_suffix = self.slack_channel_id or ''
        if channel_suffix:
            file_path = os.path.join(self.state_dir, f'last_sent_{self.job_name}_{channel_suffix}.json')
        else:
            file_path = os.path.join(self.state_dir, f'last_sent_{self.job_name}.json')

        data = {
            'last_sent_date': today,
            'last_message_hash': content_hash
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f)
            logger.info(f"[{self.job_name}] Updated dedupe state.")
        except Exception as e:
            logger.error(f"Failed to update lock file: {e}")

    def get_next_topic_candidates(self, current_topic: str) -> list:
        """Selects 3 random topics excluding the current one."""
        pool = [t for t in self.topics if t != current_topic]

        seed = int(time.time())
        count = min(3, len(pool))
        return random.sample(pool, count)

    def get_topic(self, date_seed: int, check_votes: bool = True) -> str:
        """Selects a topic based on votes or random seed."""

        if check_votes and get_winning_next_topic:
            yesterday = self._get_date(days_offset=-1)
            winner = get_winning_next_topic(yesterday, self.state_dir, job_filter=self.job_name, channel_filter=self.slack_channel_id)
            if winner:
                logger.info(f"[{self.job_name}] Using voted topic winner from {yesterday}: {winner}")
                return winner

        logger.info(f"[{self.job_name}] selecting random topic from list of {len(self.topics)} items.")

        random.seed(date_seed)
        return random.choice(self.topics)

    def generate_content(self, topic: str) -> dict:
        """Calls Bedrock to generate the content."""
        if os.environ.get('DRY_RUN') == '1' or os.environ.get('SLACK_DRY_RUN') == '1':
            logger.info('DRY_RUN detected: returning canned content without invoking Bedrock')
            return {
                "text": f"*{topic}*\n\n• This is a DRY RUN sample message for topic `{topic}`.\n• No external APIs were called.\n\nExample:\n```sql\n-- Sample code\n-- Job: {self.job_name}\n```\n\nImpact: This is a local test run.",
                "resource_url": "https://www.postgresql.org/docs/current/"
            }

        prompt = f"""{self.role_prompt}
Create a professional "{self.title_prefix}" tip about: "{topic}".

Structure for the message body:
*Topic Header*: Brief, professional one-line description of the concept (Bold, no "Topic:" prefix)
*Key Insights*: 2-3 concise, high-impact bullet points using '•' character
*Example*: Clean code snippet (5-15 lines) with inline comments (SQL or Python/etc appropriate for the topic)
*Impact*: One clear sentence explaining the business/performance value

Guidelines:
- Start the message body directly with the *Topic Header*
- Be precise and technical, avoid generic statements
- Use professional tone suitable for senior engineers
- Format for Slack: *bold* for headers, `inline code`, ```code blocks```
- Use `code` styling (backticks) for keywords, technical terms, and configuration parameters
- Keep total length under 1200 characters
- Never suggest destructive operations
- Focus on practical, immediately applicable knowledge

Output valid JSON with the following schema:
{{
  "text": "The formatted message string as per Structure guidelines",
  "resource_url": "A direct URL to the official documentation regarding the topic. If specific docs aren't found, link to the general index."
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

            if raw_content.startswith('```json'):
                raw_content = raw_content[7:]
            elif raw_content.startswith('```'):
                raw_content = raw_content[3:]
            if raw_content.endswith('```'):
                raw_content = raw_content[:-3]

            try:
                parsed = json.loads(raw_content.strip())
                if isinstance(parsed, dict) and 'text' in parsed:
                    text_value = parsed['text']
                    if isinstance(text_value, str) and text_value.strip().startswith('{'):
                        try:
                            inner_parsed = json.loads(text_value)
                            if isinstance(inner_parsed, dict) and 'text' in inner_parsed:
                                logger.warning("Detected double-encoded JSON, using inner content")
                                return inner_parsed
                        except json.JSONDecodeError:
                            pass
                    return parsed
                else:
                    logger.error(f"Unexpected JSON structure: {parsed}")
                    return {
                        "text": str(parsed) if not isinstance(parsed, dict) else json.dumps(parsed),
                        "resource_url": "https://www.postgresql.org/docs/current/"
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from model response: {e}. Falling back to raw text.")
                import re
                text_match = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_content)
                if text_match:
                    extracted_text = text_match.group(1)
                    extracted_text = extracted_text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                    url_match = re.search(r'"resource_url"\s*:\s*"([^"]*)"', raw_content)
                    url = url_match.group(1) if url_match else "https://www.postgresql.org/docs/current/"
                    return {
                        "text": extracted_text,
                        "resource_url": url
                    }
                return {
                    "text": raw_content.strip(),
                    "resource_url": "https://www.postgresql.org/docs/current/"
                }

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
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
        logger.info(f"Posting to Slack in mode={self.slack_mode} channel={self.slack_channel_id}")

        if not message_id:
            message_id = str(int(time.time() * 1000))

        meta = json.dumps({
            'message_id': message_id,
            'topic': topic,
            'job': self.job_name,
            'channel': self.slack_channel_id,
            'date': self._get_today_date()
        })

        # Note: This implementation no longer supports uploading a base64 image from an env var.
        if self.slack_mode == 'webhook':
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

            if candidates:
                blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': '*Vote for next topic:*'}})
                for i, cand in enumerate(candidates):
                    cand_meta = json.dumps({
                        'message_id': message_id,
                        'topic': topic,
                        'job': self.job_name,
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

            action_elements = [
                {'type': 'button', 'text': {'type': 'plain_text', 'text': 'Helpful', 'emoji': True}, 'action_id': 'thumbs_up', 'style': 'primary', 'value': meta},
                {'type': 'button', 'text': {'type': 'plain_text', 'text': 'Not Helpful', 'emoji': True}, 'action_id': 'thumbs_down', 'style': 'danger', 'value': meta}
            ]
            if resource_url:
                action_elements.append({'type': 'button', 'text': {'type': 'plain_text', 'text': '📖 Docs', 'emoji': True}, 'url': resource_url})
            blocks.append({'type': 'actions', 'elements': action_elements})

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

            meta = json.dumps({
                'message_id': message_id,
                'topic': topic,
                'job': self.job_name,
                'channel': self.slack_channel_id,
                'date': self._get_today_date()
            })

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

            body_section = {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': message}
            }

            blocks = [header_section]
            if header_subtitle_block:
                blocks.append(header_subtitle_block)
            blocks.extend([{'type': 'divider'}, body_section, {'type': 'divider'}])

            if candidates:
                blocks.append({
                    'type': 'section',
                    'text': {'type': 'mrkdwn', 'text': '*Vote for next topic:*'}
                })

                for i, cand in enumerate(candidates):
                    cand_meta = json.dumps({
                        'message_id': message_id,
                        'topic': topic, # current topic context
                        'job': self.job_name,
                        'channel': self.slack_channel_id,
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

                    blocks.append({
                         'type': 'context',
                         'elements': [
                             {'type': 'plain_text', 'emoji': True, 'text': 'No votes'}
                         ]
                    })

                blocks.append({'type': 'divider'})

            action_elements = [
                {
                    'type': 'button',
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

            if os.environ.get('SLACK_DRY_RUN') == '1':
                logger.info(f"Dry run - payload to send to chat.postMessage:\n{json.dumps(payload, indent=2)}")
                return

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

            date_int = int(today.replace('-', ''))

            topic = self.get_topic(date_seed=date_int)

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
    import argparse

    parser = argparse.ArgumentParser(description='Run DailyCoach jobs')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--view', action='store_true', help='Run only the Postgres (view) coach')
    group.add_argument('--data-engineering', action='store_true', help='Run only the Data Engineering coach')
    group.add_argument('--all', action='store_true', help='Run all configured coaches (default if no flag)')
    args = parser.parse_args()

    run_view = args.view or args.all or (not any([args.view, args.data_engineering, args.all]))
    run_de = args.data_engineering or args.all or (not any([args.view, args.data_engineering, args.all]))

    if run_view:
        postgres_channel = os.environ.get("SLACK_CHANNEL_ID_VIEW") or os.environ.get("SLACK_CHANNEL_ID")
        postgres_coach = DailyCoach(
            job_name="postgres",
            topics=DEFAULT_TOPICS,
            channel_id=postgres_channel,
            role_prompt="You are an expert Postgres database administrator and educator.",
            title_prefix="Daily Postgres Coach"
        )
        if postgres_coach.slack_channel_id:
            postgres_coach.run()
        else:
            logger.warning("SLACK_CHANNEL_ID_VIEW (or SLACK_CHANNEL_ID) not set; skipping Postgres Coach job.")

    if run_de:
        de_channel = os.environ.get("SLACK_CHANNEL_ID_DATA_ENG")
        if de_channel:
            de_coach = DailyCoach(
                job_name="data_engineering",
                topics=DATA_ENGINEERING_TOPICS,
                channel_id=de_channel,
                role_prompt="You are an expert Data Engineer and educator.",
                title_prefix="Daily Data Engineering Coach"
            )
            de_coach.run()
        else:
            logger.info("SLACK_CHANNEL_ID_DATA_ENG not set; skipping Data Engineering Coach job.")
