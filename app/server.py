import os
import sys
import json
import time
import hmac
import hashlib
from flask import Flask, request, jsonify, abort

from votes import record_vote

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
# Default to /app/state to match container mounts
STATE_DIR = os.environ.get('STATE_DIR', '/app/state')

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


def record_vote_payload(vote_payload: dict):
    try:
        record_vote(vote_payload, STATE_DIR)
    except Exception as e:
        app.logger.error(f"Failed to record vote: {e}")


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

    record_vote_payload(vote_payload)

    # Respond with an ephemeral confirmation
    return jsonify({
        'response_type': 'ephemeral',
        'replace_original': False,
        'text': 'Thanks — your vote was recorded.'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
