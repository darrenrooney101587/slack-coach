import os
import json
import time
import logging

logger = logging.getLogger(__name__)

def record_vote(payload: dict, state_dir: str):
    os.makedirs(state_dir, exist_ok=True)
    votes_file = os.path.join(state_dir, 'votes.json')

    try:
        if os.path.exists(votes_file):
            with open(votes_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}

    key = str(payload.get('message_id') or payload.get('ts') or payload.get('topic'))
    entry = data.get(key, {
        'message_id': payload.get('message_id'),
        'topic': payload.get('topic'),
        'date': payload.get('date'),
        'votes': []
    })

    existing = [v for v in entry['votes'] if v.get('user_id') == payload.get('user_id')]
    if existing:
        for v in entry['votes']:
            if v.get('user_id') == payload.get('user_id'):
                v['vote'] = payload.get('vote')
                v['timestamp'] = int(time.time())
    else:
        entry['votes'].append({
            'user_id': payload.get('user_id'),
            'user_name': payload.get('user_name'),
            'vote': payload.get('vote'),
            'timestamp': int(time.time())
        })

    data[key] = entry

    with open(votes_file, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Recorded vote: {payload}")


def get_vote_counts(key: str, state_dir: str):
    """Return a dict with counts for the given vote key.

    Returns: {'thumbs_up': int, 'thumbs_down': int, 'total': int}
    If no votes exist, returns zeros.
    """
    votes_file = os.path.join(state_dir, 'votes.json')
    try:
        if os.path.exists(votes_file):
            with open(votes_file, 'r') as f:
                data = json.load(f)
        else:
            return {'thumbs_up': 0, 'thumbs_down': 0, 'total': 0}
    except Exception:
        return {'thumbs_up': 0, 'thumbs_down': 0, 'total': 0}

    entry = data.get(str(key)) or {}
    votes = entry.get('votes', []) if isinstance(entry, dict) else []
    ups = sum(1 for v in votes if v.get('vote') == 'thumbs_up')
    downs = sum(1 for v in votes if v.get('vote') == 'thumbs_down')
    total = len(votes)
    return {'thumbs_up': ups, 'thumbs_down': downs, 'total': total}
