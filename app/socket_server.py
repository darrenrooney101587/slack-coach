import os
import json
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.votes import record_vote, get_vote_counts

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_APP_TOKEN = os.environ.get('SLACK_APP_TOKEN')  # xapp- token required for socket mode
STATE_DIR = os.environ.get('STATE_DIR', '/app/state')

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    logger.error('SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set for socket mode')
    raise SystemExit(1)

app = App(token=SLACK_BOT_TOKEN)


def _extract_meta_from_action(body):
    try:
        actions = body.get('actions', [])
        if not actions:
            return None
        value = actions[0].get('value')
        if not value:
            return None
        return json.loads(value)
    except Exception:
        return None


def _make_count_block(counts: dict):
    # Simple context block showing counts
    # Use unicode arrows to match button labels
    text = f"⬆️ {counts.get('thumbs_up', 0)}   ⬇️ {counts.get('thumbs_down', 0)}  total: {counts.get('total', 0)}"
    return {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": text}
        ]
    }


@app.action('thumbs_up')
def handle_thumbs_up(ack, body, client, logger):
    # Acknowledge quickly so Slack doesn't warn the user
    ack()
    user = body.get('user', {})
    meta = _extract_meta_from_action(body)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user.get('id'),
        'user_name': user.get('username') or user.get('name'),
        'vote': 'thumbs_up'
    }
    record_vote(payload, STATE_DIR)
    logger.info(f"Recorded thumbs_up for {payload}")

    # Send a short ephemeral confirmation to the clicking user
    try:
        channel_id = None
        if body.get('channel') and body['channel'].get('id'):
            channel_id = body['channel']['id']
        # Fallback: try container or view context
        if not channel_id:
            channel_id = body.get('container', {}).get('channel_id')
        if channel_id and user.get('id'):
            client.chat_postEphemeral(
                channel=channel_id,
                user=user.get('id'),
                text='Thanks — your vote was recorded.'
            )
    except Exception as e:
        logger.error(f"Failed to send ephemeral confirmation: {e}")

    # Update the original message to show new vote counts (if we can find channel & ts)
    try:
        if body.get('container') and body['container'].get('message_ts'):
            orig_ts = body['container']['message_ts']
        else:
            # fallback to actions -> message -> ts
            orig_ts = None
            if body.get('message') and body['message'].get('ts'):
                orig_ts = body['message']['ts']

        channel_id = channel_id if 'channel_id' in locals() else (body.get('channel', {}).get('id') or body.get('container', {}).get('channel_id'))
        if channel_id and orig_ts:
            counts = get_vote_counts(payload.get('message_id') or payload.get('topic') or orig_ts, STATE_DIR)
            # Build new blocks: append or replace last context block with counts
            blocks = body.get('message', {}).get('blocks', []) or []
            count_block = _make_count_block(counts)
            # If the last block is a context block with counts (heuristic), replace it
            if blocks and blocks[-1].get('type') == 'context':
                blocks[-1] = count_block
            else:
                blocks.append(count_block)

            client.chat_update(channel=channel_id, ts=orig_ts, blocks=blocks)
    except Exception as e:
        logger.error(f"Failed to update original message with counts: {e}")


@app.action('thumbs_down')
def handle_thumbs_down(ack, body, client, logger):
    ack()
    user = body.get('user', {})
    meta = _extract_meta_from_action(body)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user.get('id'),
        'user_name': user.get('username') or user.get('name'),
        'vote': 'thumbs_down'
    }
    record_vote(payload, STATE_DIR)
    logger.info(f"Recorded thumbs_down for {payload}")

    # Send ephemeral confirmation
    try:
        channel_id = None
        if body.get('channel') and body['channel'].get('id'):
            channel_id = body['channel']['id']
        if not channel_id:
            channel_id = body.get('container', {}).get('channel_id')
        if channel_id and user.get('id'):
            client.chat_postEphemeral(
                channel=channel_id,
                user=user.get('id'),
                text='Thanks — your vote was recorded.'
            )
    except Exception as e:
        logger.error(f"Failed to send ephemeral confirmation: {e}")

    # Update original message counts
    try:
        if body.get('container') and body['container'].get('message_ts'):
            orig_ts = body['container']['message_ts']
        else:
            orig_ts = None
            if body.get('message') and body['message'].get('ts'):
                orig_ts = body['message']['ts']

        channel_id = channel_id if 'channel_id' in locals() else (body.get('channel', {}).get('id') or body.get('container', {}).get('channel_id'))
        if channel_id and orig_ts:
            counts = get_vote_counts(payload.get('message_id') or payload.get('topic') or orig_ts, STATE_DIR)
            blocks = body.get('message', {}).get('blocks', []) or []
            count_block = _make_count_block(counts)
            if blocks and blocks[-1].get('type') == 'context':
                blocks[-1] = count_block
            else:
                blocks.append(count_block)

            client.chat_update(channel=channel_id, ts=orig_ts, blocks=blocks)
    except Exception as e:
        logger.error(f"Failed to update original message with counts: {e}")


if __name__ == '__main__':
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
