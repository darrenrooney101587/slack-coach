"""
Test that feedback (thumbs up/down) and votes (next topic) are stored in separate files per channel.
"""
import os
import json
from app import votes


def test_feedback_and_votes_separate_files(tmp_path, monkeypatch):
    """
    Verify that:
    1. Feedback (thumbs up/down) goes to feedback_{job}_{channel}.json
    2. Votes (next topic) go to votes_{job}_{channel}.json
    3. Each channel has its own separate files
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    
    # === VIEW Channel ===
    # Record feedback (thumbs up)
    votes.record_vote({
        'message_id': 'msg_view_1',
        'topic': 'postgres topic',
        'job': 'postgres',
        'channel': 'C_VIEW',
        'date': '2026-02-07',
        'user_id': 'alice',
        'user_name': 'Alice',
        'user_image': 'http://alice.png',
        'vote': 'thumbs_up',
        'candidate': None
    }, state_dir)
    
    # Record next topic vote
    votes.record_vote({
        'message_id': 'msg_view_1',
        'topic': 'postgres topic',
        'job': 'postgres',
        'channel': 'C_VIEW',
        'date': '2026-02-07',
        'user_id': 'bob',
        'user_name': 'Bob',
        'user_image': 'http://bob.png',
        'vote': 'vote_next_topic',
        'candidate': 'indexes'
    }, state_dir)
    
    # === Data Engineering Channel ===
    # Record feedback (thumbs down)
    votes.record_vote({
        'message_id': 'msg_de_1',
        'topic': 'spark topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG',
        'date': '2026-02-07',
        'user_id': 'charlie',
        'user_name': 'Charlie',
        'user_image': 'http://charlie.png',
        'vote': 'thumbs_down',
        'candidate': None
    }, state_dir)
    
    # Record next topic vote
    votes.record_vote({
        'message_id': 'msg_de_1',
        'topic': 'spark topic',
        'job': 'data_engineering',
        'channel': 'C_DATA_ENG',
        'date': '2026-02-07',
        'user_id': 'diana',
        'user_name': 'Diana',
        'user_image': 'http://diana.png',
        'vote': 'vote_next_topic',
        'candidate': 'airflow'
    }, state_dir)
    
    # === Verify File Structure ===
    
    # Check feedback files exist
    feedback_view = os.path.join(state_dir, 'feedback_postgres_C_VIEW.json')
    feedback_de = os.path.join(state_dir, 'feedback_data_engineering_C_DATA_ENG.json')
    
    assert os.path.exists(feedback_view), "VIEW feedback file should exist"
    assert os.path.exists(feedback_de), "DE feedback file should exist"
    
    # Check votes files exist
    votes_view = os.path.join(state_dir, 'votes_postgres_C_VIEW.json')
    votes_de = os.path.join(state_dir, 'votes_data_engineering_C_DATA_ENG.json')
    
    assert os.path.exists(votes_view), "VIEW votes file should exist"
    assert os.path.exists(votes_de), "DE votes file should exist"
    
    # === Verify Content ===
    
    # VIEW feedback should only contain thumbs up/down
    with open(feedback_view, 'r') as f:
        view_feedback_data = json.load(f)
    assert 'msg_view_1' in view_feedback_data
    assert view_feedback_data['msg_view_1']['votes'][0]['vote'] == 'thumbs_up'
    assert view_feedback_data['msg_view_1']['votes'][0]['user_id'] == 'alice'
    
    # VIEW votes should only contain next topic votes
    with open(votes_view, 'r') as f:
        view_votes_data = json.load(f)
    assert 'msg_view_1' in view_votes_data
    assert view_votes_data['msg_view_1']['votes'][0]['vote'] == 'vote_next_topic'
    assert view_votes_data['msg_view_1']['votes'][0]['candidate'] == 'indexes'
    assert view_votes_data['msg_view_1']['votes'][0]['user_id'] == 'bob'
    
    # DE feedback should only contain thumbs up/down
    with open(feedback_de, 'r') as f:
        de_feedback_data = json.load(f)
    assert 'msg_de_1' in de_feedback_data
    assert de_feedback_data['msg_de_1']['votes'][0]['vote'] == 'thumbs_down'
    assert de_feedback_data['msg_de_1']['votes'][0]['user_id'] == 'charlie'
    
    # DE votes should only contain next topic votes
    with open(votes_de, 'r') as f:
        de_votes_data = json.load(f)
    assert 'msg_de_1' in de_votes_data
    assert de_votes_data['msg_de_1']['votes'][0]['vote'] == 'vote_next_topic'
    assert de_votes_data['msg_de_1']['votes'][0]['candidate'] == 'airflow'
    assert de_votes_data['msg_de_1']['votes'][0]['user_id'] == 'diana'
    
    print("\n✅ SUCCESS: Feedback and votes are properly separated by channel!")
    print(f"   VIEW feedback: {feedback_view}")
    print(f"   VIEW votes: {votes_view}")
    print(f"   DE feedback: {feedback_de}")
    print(f"   DE votes: {votes_de}")


def test_get_vote_counts_uses_feedback_file(tmp_path, monkeypatch):
    """
    Verify that get_vote_counts reads from feedback file, not votes file
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    
    # Create a feedback file
    feedback_file = os.path.join(state_dir, 'feedback_postgres_C123.json')
    feedback_data = {
        'msg1': {
            'message_id': 'msg1',
            'topic': 'test',
            'job': 'postgres',
            'channel': 'C123',
            'date': '2026-02-07',
            'votes': [
                {'user_id': 'u1', 'vote': 'thumbs_up', 'timestamp': 1},
                {'user_id': 'u2', 'vote': 'thumbs_up', 'timestamp': 2},
                {'user_id': 'u3', 'vote': 'thumbs_down', 'timestamp': 3}
            ]
        }
    }
    with open(feedback_file, 'w') as f:
        json.dump(feedback_data, f)
    
    # Get vote counts - should read from feedback file
    counts = votes.get_vote_counts('msg1', state_dir, job='postgres', channel='C123')
    
    assert counts['thumbs_up'] == 2
    assert counts['thumbs_down'] == 1
    assert counts['total'] == 3


def test_get_winning_next_topic_uses_votes_file(tmp_path, monkeypatch):
    """
    Verify that get_winning_next_topic reads from votes file, not feedback file
    """
    state_dir = str(tmp_path)
    monkeypatch.setenv('STATE_DIR', state_dir)
    
    # Create a votes file (NOT feedback file)
    votes_file = os.path.join(state_dir, 'votes_postgres_C123.json')
    votes_data = {
        'msg1': {
            'message_id': 'msg1',
            'topic': 'test',
            'job': 'postgres',
            'channel': 'C123',
            'date': '2026-02-07',
            'votes': [
                {'user_id': 'u1', 'vote': 'vote_next_topic', 'candidate': 'indexes', 'timestamp': 1},
                {'user_id': 'u2', 'vote': 'vote_next_topic', 'candidate': 'indexes', 'timestamp': 2},
                {'user_id': 'u3', 'vote': 'vote_next_topic', 'candidate': 'vacuum', 'timestamp': 3}
            ]
        }
    }
    with open(votes_file, 'w') as f:
        json.dump(votes_data, f)
    
    # Get winning topic - should read from votes file
    winner = votes.get_winning_next_topic('2026-02-07', state_dir, job_filter='postgres', channel_filter='C123')
    
    assert winner == 'indexes'
