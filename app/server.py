import os
import sys
import json
import time
import hmac
import hashlib
from flask import Flask, request, jsonify, abort

from votes import record_vote
from fireflies import verify_fireflies_signature, fetch_transcript
from formatter import format_recap
from router import resolve_channel, load_routing_config
from slack import post_recap

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
STATE_DIR = os.environ.get('STATE_DIR', '/app/state')
FIREFLIES_WEBHOOK_SECRET = os.environ.get("FIREFLIES_WEBHOOK_SECRET")
FIREFLIES_API_KEY = os.environ.get("FIREFLIES_API_KEY")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
ROUTING_CONFIG_FILE = os.environ.get("ROUTING_CONFIG_FILE", "/app/routing.yml")

if not SLACK_SIGNING_SECRET:
    print('Warning: SLACK_SIGNING_SECRET is not set. Incoming Slack requests will not be verified.', file=sys.stderr)

_routing_config = None


def _get_routing_config():
    global _routing_config
    if _routing_config is None:
        try:
            _routing_config = load_routing_config(ROUTING_CONFIG_FILE)
        except Exception as e:
            app.logger.error(f"Failed to load routing config: {e}")
            _routing_config = {}
    return _routing_config


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
    user = data.get('user', {})
    actions = data.get('actions', [])
    if not actions:
        return jsonify({'ok': False}), 400

    action = actions[0]
    try:
        meta = json.loads(action.get('value', '{}'))
    except Exception:
        meta = {}

    action_id = action.get('action_id')
    if action_id.startswith('vote_next_topic'):
        vote_type = 'vote_next_topic'
    else:
        vote_type = action_id

    vote_payload = {
        'message_id': meta.get('message_id') or data.get('container', {}).get('message_ts') or meta.get('ts'),
        'topic': meta.get('topic'),
        'job': meta.get('job'),  # Extract job/category for filtering
        'channel': meta.get('channel') or data.get('container', {}).get('channel_id') or (data.get('message') or {}).get('channel'),
        'candidate': meta.get('candidate'),
        'date': meta.get('date'),
        'user_id': user.get('id'),
        'user_name': user.get('username') or user.get('name'),
        'vote': vote_type
    }

    record_vote_payload(vote_payload)

    response_text = 'Thanks — your vote was recorded.'
    if vote_payload['vote'] == 'vote_next_topic' and vote_payload['candidate']:
         response_text = f"Thanks! You voted for: {vote_payload['candidate']}"

    return jsonify({
        'response_type': 'ephemeral',
        'replace_original': False,
        'text': response_text
    })


@app.route("/webhooks/fireflies", methods=["POST"])
def fireflies_webhook():
    raw_body = request.get_data()

    if FIREFLIES_WEBHOOK_SECRET:
        sig = request.headers.get("x-hub-signature", "")
        if not verify_fireflies_signature(FIREFLIES_WEBHOOK_SECRET, raw_body, sig):
            abort(403)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    meeting_id = payload.get("meetingId")
    if not meeting_id:
        return jsonify({"ok": False, "error": "missing_meetingId"}), 400

    event_type = payload.get("eventType", "")
    if event_type != "Transcription completed":
        return jsonify({"ok": True, "skipped": True}), 200

    if not FIREFLIES_API_KEY:
        return jsonify({"ok": False, "error": "no_api_key"}), 500

    transcript = fetch_transcript(meeting_id, FIREFLIES_API_KEY)

    summary = transcript.get("summary") or {}
    has_summary = any([
        summary.get("overview"),
        summary.get("bullet_gist"),
        summary.get("action_items"),
    ])
    if not has_summary or not transcript.get("transcript_url"):
        return jsonify({"ok": False, "error": "missing_required_fields"}), 422

    blocks = format_recap(transcript)
    config = _get_routing_config()
    channel_id = resolve_channel(transcript, config)

    if not channel_id:
        return jsonify({"ok": False, "error": "no_routing_target"}), 500

    if not SLACK_BOT_TOKEN:
        return jsonify({"ok": False, "error": "no_bot_token"}), 500

    try:
        post_recap(blocks, channel_id, SLACK_BOT_TOKEN)
    except RuntimeError as e:
        error_str = str(e)
        if "not_in_channel" in error_str:
            return jsonify({"ok": False, "error": "bot_not_in_channel", "channel": channel_id}), 403
        app.logger.error(f"Slack posting failed: {e}")
        return jsonify({"ok": False, "error": "slack_post_failed"}), 500

    return jsonify({"ok": True}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
