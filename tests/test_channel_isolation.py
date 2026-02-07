"""
Integration test to verify complete isolation between channels:
- Separate last_sent_*.json files per channel
- Votes filtered by channel when determining winners
"""
import os
import json
import tempfile
from app.main import DailyCoach
from app import votes


def test_complete_channel_isolation(tmp_path, monkeypatch):
    """
    Verify that two channels (VIEW and DATA_ENG) maintain completely isolated state:
    1. Dedupe files are separate
    2. Vote winners are calculated independently
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('BEDROCK_MODEL_ID', 'mock-model')
    monkeypatch.setenv('SLACK_MODE', 'webhook')
    monkeypatch.setenv('SLACK_WEBHOOK_URL', 'https://example.com')
    monkeypatch.setenv('DEDUPE_ENABLED', 'true')

    # Create two coaches for different channels
    coach_view = DailyCoach(
        job_name='postgres',
        topics=['topic_a', 'topic_b'],
        channel_id='C_VIEW',
        role_prompt='Postgres expert',
        title_prefix='Postgres Coach'
    )
    
    coach_de = DailyCoach(
        job_name='data_engineering',
        topics=['topic_x', 'topic_y'],
        channel_id='C_DATA_ENG',
        role_prompt='DE expert',
        title_prefix='DE Coach'
    )

    # 1. TEST: Dedupe files are separate
    today = '2026-02-07'
    coach_view.update_dedupe_state(today, 'hash_view')
    coach_de.update_dedupe_state(today, 'hash_de')

    view_dedupe_file = os.path.join(state_dir, 'last_sent_postgres_C_VIEW.json')
    de_dedupe_file = os.path.join(state_dir, 'last_sent_data_engineering_C_DATA_ENG.json')

    assert os.path.exists(view_dedupe_file), "VIEW dedupe file should exist"
    assert os.path.exists(de_dedupe_file), "DE dedupe file should exist"

    with open(view_dedupe_file, 'r') as f:
        view_data = json.load(f)
    with open(de_dedupe_file, 'r') as f:
        de_data = json.load(f)

    assert view_data['last_message_hash'] == 'hash_view'
    assert de_data['last_message_hash'] == 'hash_de'

    # 2. TEST: Votes are filtered by channel
    # Votes are now stored in separate files per channel
    votes_file_view = os.path.join(state_dir, 'votes_postgres_C_VIEW.json')
    votes_file_de = os.path.join(state_dir, 'votes_data_engineering_C_DATA_ENG.json')
    
    # Simulate votes from VIEW channel
    votes_data_view = {
        'msg_view': {
            'message_id': 'msg_view',
            'topic': 'postgres_topic',
            'job': 'postgres',
            'channel': 'C_VIEW',
            'date': '2026-02-06',
            'votes': [
                {'user_id': 'u1', 'vote': 'vote_next_topic', 'candidate': 'indexes', 'timestamp': 1},
                {'user_id': 'u2', 'vote': 'vote_next_topic', 'candidate': 'indexes', 'timestamp': 2},
                {'user_id': 'u3', 'vote': 'vote_next_topic', 'candidate': 'vacuum', 'timestamp': 3}
            ]
        }
    }
    
    # Simulate votes from DE channel
    votes_data_de = {
        'msg_de': {
            'message_id': 'msg_de',
            'topic': 'de_topic',
            'job': 'data_engineering',
            'channel': 'C_DATA_ENG',
            'date': '2026-02-06',
            'votes': [
                {'user_id': 'u4', 'vote': 'vote_next_topic', 'candidate': 'spark', 'timestamp': 1},
                {'user_id': 'u5', 'vote': 'vote_next_topic', 'candidate': 'spark', 'timestamp': 2},
                {'user_id': 'u6', 'vote': 'vote_next_topic', 'candidate': 'spark', 'timestamp': 3},
                {'user_id': 'u7', 'vote': 'vote_next_topic', 'candidate': 'airflow', 'timestamp': 4}
            ]
        }
    }
    
    with open(votes_file_view, 'w') as f:
        json.dump(votes_data_view, f)
    
    with open(votes_file_de, 'w') as f:
        json.dump(votes_data_de, f)

    # Get winners for each channel - should be different
    winner_view = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='postgres',
        channel_filter='C_VIEW'
    )
    
    winner_de = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='data_engineering',
        channel_filter='C_DATA_ENG'
    )

    assert winner_view == 'indexes', f"VIEW channel should have 'indexes' as winner, got {winner_view}"
    assert winner_de == 'spark', f"DE channel should have 'spark' as winner, got {winner_de}"

    # 3. TEST: Cross-channel interference doesn't happen
    # Even if DE channel ran first, VIEW channel should see its own winner
    winner_view_again = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='postgres',
        channel_filter='C_VIEW'
    )
    assert winner_view_again == 'indexes', "VIEW winner should remain stable"


def test_no_cross_channel_vote_pollution(tmp_path, monkeypatch):
    """
    Ensure that recording a vote for one channel doesn't affect another channel's vote count
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    
    # Record vote for VIEW channel
    votes.record_vote({
        'message_id': 'msg1',
        'topic': 'test_topic',
        'job': 'postgres',
        'channel': 'C_VIEW',
        'date': '2026-02-07',
        'user_id': 'user1',
        'user_name': 'User One',
        'vote': 'vote_next_topic',
        'candidate': 'topic_a'
    }, state_dir)
    
    # Record vote for DE channel (same message_id to test isolation)
    votes.record_vote({
        'message_id': 'msg2',
        'topic': 'test_topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG',
        'date': '2026-02-07',
        'user_id': 'user2',
        'user_name': 'User Two',
        'vote': 'vote_next_topic',
        'candidate': 'topic_b'
    }, state_dir)
    
    # Verify winners are independent
    winner_view = votes.get_winning_next_topic(
        '2026-02-07',
        state_dir,
        job_filter='postgres',
        channel_filter='C_VIEW'
    )
    
    winner_de = votes.get_winning_next_topic(
        '2026-02-07',
        state_dir,
        job_filter='data_engineering',
        channel_filter='C_DATA_ENG'
    )
    
    assert winner_view == 'topic_a'
    assert winner_de == 'topic_b'
