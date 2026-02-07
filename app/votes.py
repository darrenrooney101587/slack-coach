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
        'job': payload.get('job'),
        'date': payload.get('date'),
        'votes': []
    })

    existing = [v for v in entry['votes'] if v.get('user_id') == payload.get('user_id')]
    if existing:
        for v in entry['votes']:
            if v.get('user_id') == payload.get('user_id'):
                v['vote'] = payload.get('vote')
                v['candidate'] = payload.get('candidate')
                v['timestamp'] = int(time.time())
                if payload.get('user_image'):
                    v['user_image'] = payload.get('user_image')
    else:
        entry['votes'].append({
            'user_id': payload.get('user_id'),
            'user_name': payload.get('user_name'),
            'user_image': payload.get('user_image'),
            'vote': payload.get('vote'),
            'candidate': payload.get('candidate'),
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

    # Collect recent voter images (limit to 3 for clean UI)
    recent_images = []
    seen = set()
    # Sort by timestamp descending to show most recent voters
    for v in sorted(votes, key=lambda x: x.get('timestamp', 0), reverse=True):
        uid = v.get('user_id')
        img = v.get('user_image')
        if uid and img and uid not in seen:
            recent_images.append({'image_url': img, 'alt_text': v.get('user_name', 'User')})
            seen.add(uid)
            if len(recent_images) >= 3:
                break

    return {
        'thumbs_up': ups,
        'thumbs_down': downs,
        'total': total,
        'recent_images': recent_images
    }


def get_poll_details(key: str, candidates: list, state_dir: str):
    """
    Returns specific vote counts and user images for a list of candidates
    for a specific message (key).
    Returns: { 'Candidate A': {'count': 5, 'images': [...]}, ... }
    """
    votes_file = os.path.join(state_dir, 'votes.json')
    data = {}
    try:
        if os.path.exists(votes_file):
            with open(votes_file, 'r') as f:
                data = json.load(f)
    except Exception:
        pass

    entry = data.get(str(key)) or {}
    all_votes = entry.get('votes', []) if isinstance(entry, dict) else []

    result = {}
    for cand in candidates:
        # Filter votes for this candidate where vote type is 'vote_next_topic'
        cand_votes = [v for v in all_votes if v.get('vote') == 'vote_next_topic' and v.get('candidate') == cand]

        count = len(cand_votes)

        # Collect recent images
        recent_images = []
        seen = set()
        # Sort desc by timestamp
        for v in sorted(cand_votes, key=lambda x: x.get('timestamp', 0), reverse=True):
            uid = v.get('user_id')
            img = v.get('user_image')
            if uid and img and uid not in seen:
                recent_images.append({'image_url': img, 'alt_text': v.get('user_name', 'User')})
                seen.add(uid)
                if len(recent_images) >= 3:
                    break

        result[cand] = {
            'count': count,
            'recent_images': recent_images
        }

    return result


def get_winning_next_topic(date: str, state_dir: str, job_filter: str = None):
    """
    Finds the winning 'next topic' vote for a given date's message.
    The 'date' argument refers to the date the voting message was SENT (i.e., yesterday).
    Optional job_filter ensures we only count votes for the specific coach job (Postgres vs DataEng).
    """
    votes_file = os.path.join(state_dir, 'votes.json')
    try:
        if os.path.exists(votes_file):
            with open(votes_file, 'r') as f:
                data = json.load(f)
        else:
            return None
    except Exception:
        return None

    # Find entries for the given date
    # (The key is somewhat arbitrary, usually message_id or timestamp, so we search values)

    # We are looking for votes cast ON the message from 'date'.
    # Our data structure is keyed by message_id.
    # We need to find the message(s) where entry['date'] == date.

    candidates_counts = {}

    for key, entry in data.items():
        if entry.get('date') == date:
            # If job_filter is provided (e.g. 'postgres'), verify this message belongs to that job
            if job_filter and entry.get('job') != job_filter:
                continue

            for v in entry.get('votes', []):
                if v.get('vote') == 'vote_next_topic' and v.get('candidate'):
                    cand = v.get('candidate')
                    candidates_counts[cand] = candidates_counts.get(cand, 0) + 1

    if not candidates_counts:
        return None

    # Return the candidate with the most votes
    # Sort by count (desc) then by name (asc) for determinism
    sorted_candidates = sorted(candidates_counts.items(), key=lambda x: (-x[1], x[0]))
    return sorted_candidates[0][0]
