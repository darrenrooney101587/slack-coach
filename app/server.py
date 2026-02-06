import os
import sys
import json
import time
import hmac
import hashlib
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
STATE_DIR = os.environ.get('STATE_DIR', '/state')

if not SLACK_SIGNING_SECRET:
    print('Warning: SLACK_SIGNING_SECRET is not set. Incoming Slack requests will not be verified.', file=sys.stderr)


def verify_slack_request(req):
    if not SLACK_SIGNING_SECRET:
        return True

    timestamp = req.headers.get('X-Slack-Request-Timestamp')
    if not timestamp:
        return False

    # prevent replay
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}".encode('utf-8')
    my_sig = 'v0=' + hmac.new(SLACK_SIGNING_SECRET.encode('utf-8'), sig_basestring, hashlib.sha256).hexdigest()
    slack_signature = req.headers.get('X-Slack-Signature', '')
    return hmac.compare_digest(my_sig, slack_signature)


def record_vote(vote_payload: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    votes_file = os.path.join(STATE_DIR, 'votes.json')

    try:
        if os.path.exists(votes_file):
            with open(votes_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}

    # Structure vote_payload: {message_id, topic, date, user_id, user_name, vote}
    key = f"{vote_payload.get('message_id')}"
    entry = data.get(key, {
        'message_id': vote_payload.get('message_id'),
        'topic': vote_payload.get('topic'),
        'date': vote_payload.get('date'),
        'votes': []
    })
    # prevent duplicate votes from same user for same message
    existing = [v for v in entry['votes'] if v.get('user_id') == vote_payload.get('user_id')]
    if existing:
        # update existing vote
        for v in entry['votes']:
            if v.get('user_id') == vote_payload.get('user_id'):
                v['vote'] = vote_payload.get('vote')
                v['timestamp'] = int(time.time())
    else:
        entry['votes'].append({
            'user_id': vote_payload.get('user_id'),
            'user_name': vote_payload.get('user_name'),
            'vote': vote_payload.get('vote'),
            'timestamp': int(time.time())
        })

    data[key] = entry

    with open(votes_file, 'w') as f:
        json.dump(data, f, indent=2)


@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    if not verify_slack_request(request):
        abort(403)

    payload = request.form.get('payload')
    if not payload:
        return jsonify({'ok': False}), 400

    data = json.loads(payload)
    # interactive button payload
    user = data.get('user', {})
    actions = data.get('actions', [])
    if not actions:
        return jsonify({'ok': False}), 400

    action = actions[0]
    # We expect action['value'] to be JSON with message metadata
    try:
        meta = json.loads(action.get('value', '{}'))
    except Exception:
        meta = {}

    vote_payload = {
        'message_id': meta.get('message_id') or data.get('container', {}).get('message_ts') or meta.get('ts'),
        'topic': meta.get('topic'),
        'date': meta.get('date'),
        'user_id': user.get('id'),
        'user_name': user.get('username') or user.get('name'),
        'vote': action.get('action_id')  # 'thumbs_up' or 'thumbs_down'
    }

    record_vote(vote_payload)

    # Respond with an ephemeral confirmation
    return jsonify({
        'response_type': 'ephemeral',
        'replace_original': False,
        'text': 'Thanks — your vote was recorded.'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
