import os
import json
import tempfile
from app.main import DailyCoach
from app import votes


def test_channel_dedupe_file_written(tmp_path, monkeypatch):
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('BEDROCK_MODEL_ID', 'mock-model')
    monkeypatch.setenv('SLACK_MODE', 'webhook')
    monkeypatch.setenv('SLACK_WEBHOOK_URL', 'https://example.com')

    coach = DailyCoach(job_name='postgres', topics=['a'], channel_id='CCHAN', role_prompt='x', title_prefix='Test')
    today = '2026-02-07'
    coach.update_dedupe_state(today, 'hash123')

    expected = os.path.join(state_dir, 'last_sent_postgres_CCHAN.json')
    assert os.path.exists(expected)
    with open(expected, 'r') as f:
        data = json.load(f)
    assert data['last_sent_date'] == today
    assert data['last_message_hash'] == 'hash123'


def test_record_vote_and_winner_filters(tmp_path, monkeypatch):
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    os.makedirs(state_dir, exist_ok=True)

    # Create separate votes files for each channel (new structure)
    votes_file_c1 = os.path.join(state_dir, 'votes_postgres_C1.json')
    votes_file_c2 = os.path.join(state_dir, 'votes_postgres_C2.json')

    # Entry for channel C1
    entry1 = {
        'message_id': 'm1',
        'topic': 't1',
        'job': 'postgres',
        'channel': 'C1',
        'date': '2026-02-06',
        'votes': [
            {'user_id': 'u1', 'vote': 'vote_next_topic', 'candidate': 'A', 'timestamp': 1}
        ]
    }
    
    # Entry for channel C2
    entry2 = {
        'message_id': 'm2',
        'topic': 't1',
        'job': 'postgres',
        'channel': 'C2',
        'date': '2026-02-06',
        'votes': [
            {'user_id': 'u2', 'vote': 'vote_next_topic', 'candidate': 'B', 'timestamp': 1},
            {'user_id': 'u3', 'vote': 'vote_next_topic', 'candidate': 'B', 'timestamp': 2}
        ]
    }
    
    with open(votes_file_c1, 'w') as f:
        json.dump({'m1': entry1}, f)
    
    with open(votes_file_c2, 'w') as f:
        json.dump({'m2': entry2}, f)

    # No filter -> should look in votes.json (legacy) which doesn't exist, returns None
    winner_all = votes.get_winning_next_topic('2026-02-06', state_dir)
    assert winner_all is None  # No legacy file exists

    # Filter by channel C1 -> winner A
    winner_c1 = votes.get_winning_next_topic('2026-02-06', state_dir, job_filter='postgres', channel_filter='C1')
    assert winner_c1 == 'A'

    # Filter by channel C2 -> winner B
    winner_c2 = votes.get_winning_next_topic('2026-02-06', state_dir, job_filter='postgres', channel_filter='C2')
    assert winner_c2 == 'B'
