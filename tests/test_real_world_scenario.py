"""
Real-world scenario test: Demonstrates that VIEW and Data Engineering 
can run independently even if one runs before the other.
"""
import os
import json
from app.main import DailyCoach
from app import votes


def test_view_runs_then_de_runs_independently(tmp_path, monkeypatch):
    """
    Simulates the exact scenario from the user's request:
    - VIEW (database team) runs and creates voting feedback
    - Data Engineering runs later
    - DE should NOT be affected by VIEW's previous run
    - Each should see their own vote winners
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('BEDROCK_MODEL_ID', 'mock-model')
    monkeypatch.setenv('SLACK_MODE', 'webhook')
    monkeypatch.setenv('SLACK_WEBHOOK_URL', 'https://example.com')
    monkeypatch.setenv('DEDUPE_ENABLED', 'true')

    # === STEP 1: VIEW team runs their daily coach ===
    view_coach = DailyCoach(
        job_name='postgres',
        topics=['indexes', 'vacuum', 'partitioning'],
        channel_id='C_VIEW_TEAM',
        role_prompt='Postgres expert',
        title_prefix='Postgres Coach'
    )
    
    # Simulate VIEW coach running on 2026-02-07
    today_view = '2026-02-07'
    view_coach.update_dedupe_state(today_view, 'hash_view_feb7')
    
    # Simulate users voting on VIEW's message from Feb 6
    votes.record_vote({
        'message_id': 'view_msg_feb6',
        'topic': 'current_view_topic',
        'job': 'postgres',
        'channel': 'C_VIEW_TEAM',
        'date': '2026-02-06',
        'user_id': 'alice',
        'user_name': 'Alice',
        'vote': 'vote_next_topic',
        'candidate': 'indexes'
    }, state_dir)
    
    votes.record_vote({
        'message_id': 'view_msg_feb6',
        'topic': 'current_view_topic',
        'job': 'postgres',
        'channel': 'C_VIEW_TEAM',
        'date': '2026-02-06',
        'user_id': 'bob',
        'user_name': 'Bob',
        'vote': 'vote_next_topic',
        'candidate': 'indexes'
    }, state_dir)
    
    # VIEW winner should be 'indexes'
    view_winner = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='postgres',
        channel_filter='C_VIEW_TEAM'
    )
    assert view_winner == 'indexes', f"VIEW should have 'indexes' as winner, got {view_winner}"
    
    # === STEP 2: Data Engineering team runs LATER (same day or different day) ===
    de_coach = DailyCoach(
        job_name='data_engineering',
        topics=['spark', 'airflow', 'dbt'],
        channel_id='C_DATA_ENG_TEAM',
        role_prompt='DE expert',
        title_prefix='DE Coach'
    )
    
    # DE coach runs
    today_de = '2026-02-07'
    de_coach.update_dedupe_state(today_de, 'hash_de_feb7')
    
    # Simulate DE users voting on DE's message from Feb 6
    votes.record_vote({
        'message_id': 'de_msg_feb6',
        'topic': 'current_de_topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG_TEAM',
        'date': '2026-02-06',
        'user_id': 'charlie',
        'user_name': 'Charlie',
        'vote': 'vote_next_topic',
        'candidate': 'spark'
    }, state_dir)
    
    votes.record_vote({
        'message_id': 'de_msg_feb6',
        'topic': 'current_de_topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG_TEAM',
        'date': '2026-02-06',
        'user_id': 'diana',
        'user_name': 'Diana',
        'vote': 'vote_next_topic',
        'candidate': 'spark'
    }, state_dir)
    
    votes.record_vote({
        'message_id': 'de_msg_feb6',
        'topic': 'current_de_topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG_TEAM',
        'date': '2026-02-06',
        'user_id': 'eve',
        'user_name': 'Eve',
        'vote': 'vote_next_topic',
        'candidate': 'spark'
    }, state_dir)
    
    # === STEP 3: Verify complete isolation ===
    
    # DE winner should be 'spark' (NOT affected by VIEW's votes)
    de_winner = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='data_engineering',
        channel_filter='C_DATA_ENG_TEAM'
    )
    assert de_winner == 'spark', f"DE should have 'spark' as winner, got {de_winner}"
    
    # VIEW winner should STILL be 'indexes' (NOT affected by DE's votes)
    view_winner_check = votes.get_winning_next_topic(
        '2026-02-06',
        state_dir,
        job_filter='postgres',
        channel_filter='C_VIEW_TEAM'
    )
    assert view_winner_check == 'indexes', f"VIEW winner should remain 'indexes', got {view_winner_check}"
    
    # Verify separate dedupe files exist
    view_dedupe = os.path.join(state_dir, 'last_sent_postgres_C_VIEW_TEAM.json')
    de_dedupe = os.path.join(state_dir, 'last_sent_data_engineering_C_DATA_ENG_TEAM.json')
    
    assert os.path.exists(view_dedupe), "VIEW dedupe file should exist"
    assert os.path.exists(de_dedupe), "DE dedupe file should exist"
    
    with open(view_dedupe, 'r') as f:
        view_state = json.load(f)
    with open(de_dedupe, 'r') as f:
        de_state = json.load(f)
    
    assert view_state['last_sent_date'] == today_view
    assert view_state['last_message_hash'] == 'hash_view_feb7'
    assert de_state['last_sent_date'] == today_de
    assert de_state['last_message_hash'] == 'hash_de_feb7'
    
    # Verify they maintain separate state even if one ran first
    print("\n✅ SUCCESS: VIEW and DE maintain completely separate state!")
    print(f"   VIEW winner: {view_winner_check}")
    print(f"   DE winner: {de_winner}")
    print(f"   VIEW dedupe: {view_dedupe}")
    print(f"   DE dedupe: {de_dedupe}")
