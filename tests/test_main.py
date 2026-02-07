import os
import pytest
import json
from unittest.mock import MagicMock, patch, mock_open
import sys

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.main import DailyCoach

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-v2")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/XXX/YYY/ZZZ")
    monkeypatch.setenv("SLACK_MODE", "webhook")
    monkeypatch.setenv("STATE_DIR", "/tmp/test_state")

@pytest.fixture
def coach_args():
    return {
        "job_name": "test_job",
        "topics": ["topic1", "topic2"],
        "channel_id": "C123",
        "role_prompt": "You are a tester.",
        "title_prefix": "Test Coach"
    }

def test_init_raises_without_env(monkeypatch, coach_args):
    monkeypatch.delenv("AWS_REGION", raising=False)
    with pytest.raises(ValueError, match="Missing AWS_REGION"):
        DailyCoach(**coach_args)

def test_init_success(mock_env, coach_args):
    coach = DailyCoach(**coach_args)
    assert coach.aws_region == "us-east-1"
    assert coach.slack_mode == "webhook"

@patch('app.main.boto3.client')
def test_generate_content_success(mock_boto, mock_env, coach_args):
    coach = DailyCoach(**coach_args)

    mock_response = {
        'body': MagicMock(read=lambda: json.dumps({
            'content': [{'text': json.dumps({
                'text': 'Test Message',
                'resource_url': 'http://example.com'
            })}]
        }).encode('utf-8'))
    }
    mock_boto.return_value.invoke_model.return_value = mock_response

    result = coach.generate_content("test topic")
    assert result['text'] == 'Test Message'
    assert result['resource_url'] == 'http://example.com'

@patch('app.main.requests.post')
def test_post_to_slack_webhook(mock_post, mock_env, coach_args):
    coach = DailyCoach(**coach_args)
    coach.post_to_slack("My message", topic="test", message_id="123")

    args, kwargs = mock_post.call_args
    assert args[0] == "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    payload = kwargs['json']
    assert "My message" in str(payload)

def test_dedupe_check(mock_env, monkeypatch, coach_args):
    monkeypatch.setenv("DEDUPE_ENABLED", "true")
    coach = DailyCoach(**coach_args)

    # Mocking file existence and open
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps({"last_sent_date": "2026-02-07"}))):

        is_dupe = coach.check_dedupe("2026-02-07")
        assert is_dupe is True

        is_dupe = coach.check_dedupe("2026-02-08")
        assert is_dupe is False

@patch('app.main.DailyCoach.post_to_slack')
@patch('app.main.DailyCoach.generate_content')
@patch('app.main.DailyCoach.get_topic')
@patch('app.main.DailyCoach.check_dedupe')
def test_run_flow(mock_dedupe, mock_get_topic, mock_gen, mock_post, mock_env, coach_args):
    mock_dedupe.return_value = False
    mock_get_topic.return_value = "Test Topic"
    mock_gen.return_value = {"text": "Content", "resource_url": "url"}

    coach = DailyCoach(**coach_args)
    # Mock update_dedupe_state to avoid writing to disk
    with patch.object(coach, 'update_dedupe_state'):
         coach.run()

    mock_get_topic.assert_called_once()
    mock_gen.assert_called_once_with("Test Topic")
    mock_post.assert_called_once()
