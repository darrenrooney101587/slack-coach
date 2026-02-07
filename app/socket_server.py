import os
import re
import json
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.votes import record_vote, get_vote_counts, get_poll_details

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


def _get_user_image(client, user_id):
    try:
        resp = client.users_info(user=user_id)
        if resp.get('ok'):
            return resp['user']['profile'].get('image_48') # 48x48 is standard for context blocks
    except Exception as e:
        logger.warning(f"Failed to fetch user info for {user_id}: {e}")
    return None


def _make_count_block(counts: dict):
    # Context block showing counts and recent voter avatars
    elements = []

    # Add recent voter images
    for img in counts.get('recent_images', []):
        elements.append({
            "type": "image",
            "image_url": img['image_url'],
            "alt_text": img['alt_text']
        })

    text = f"Total Votes: {counts.get('total', 0)} (⬆️ {counts.get('thumbs_up', 0)} / ⬇️ {counts.get('thumbs_down', 0)})"
    elements.append({"type": "plain_text", "emoji": True, "text": text})

    return {
        "type": "context",
        "elements": elements
    }


def _make_poll_context_block(details: dict):
    # details = {'count': int, 'recent_images': [...]}
    elements = []

    # Add recent voter images for this candidate
    for img in details.get('recent_images', []):
        elements.append({
            "type": "image",
            "image_url": img['image_url'],
            "alt_text": img['alt_text']
        })

    count = details.get('count', 0)
    text = f"{count} vote{'s' if count != 1 else ''}" if count > 0 else "No votes"
    elements.append({"type": "plain_text", "emoji": True, "text": text})

    return {
        "type": "context",
        "elements": elements
    }


@app.action('thumbs_up')
def handle_thumbs_up(ack, body, client, logger):
    ack()
    user = body.get('user', {})
    user_id = user.get('id')
    user_image = _get_user_image(client, user_id)

    meta = _extract_meta_from_action(body)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': user_image,
        'vote': 'thumbs_up'
    }
    record_vote(payload, STATE_DIR)
    logger.info(f"Recorded thumbs_up for {payload}")

    # Update the buttons to show acknowledgement
    try:
        if body.get('message'):
            blocks = body['message'].get('blocks', [])
            # Find the actions block at the end (usually last block or second to last)
            for block in reversed(blocks):
                if block['type'] == 'actions':
                    for element in block.get('elements', []):
                        if element.get('action_id') == 'thumbs_up':
                            element['text']['text'] = 'Helpful   :white_check_mark:'
                        elif element.get('action_id') == 'thumbs_down':
                            # Reset the other one if needed, or keep as is
                            element['text']['text'] = 'Not Helpful   :thumbsdown:'

                    # Update the message
                    channel_id = body.get('channel', {}).get('id')
                    ts = body.get('message', {}).get('ts')
                    if channel_id and ts:
                        client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
                    break
    except Exception as e:
        logger.error(f"Failed to update message buttons: {e}")


@app.action('thumbs_down')
def handle_thumbs_down(ack, body, client, logger):
    ack()
    user = body.get('user', {})
    user_id = user.get('id')
    user_image = _get_user_image(client, user_id)

    meta = _extract_meta_from_action(body)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': user_image,
        'vote': 'thumbs_down'
    }
    record_vote(payload, STATE_DIR)
    logger.info(f"Recorded thumbs_down for {payload}")

    # Update the buttons to show acknowledgement
    try:
        if body.get('message'):
            blocks = body['message'].get('blocks', [])
            for block in reversed(blocks):
                if block['type'] == 'actions':
                    for element in block.get('elements', []):
                        if element.get('action_id') == 'thumbs_down':
                            element['text']['text'] = 'Not Helpful   :white_check_mark:'
                        elif element.get('action_id') == 'thumbs_up':
                            element['text']['text'] = 'Helpful   :thumbsup:'

                    channel_id = body.get('channel', {}).get('id')
                    ts = body.get('message', {}).get('ts')
                    if channel_id and ts:
                        client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
                    break
    except Exception as e:
        logger.error(f"Failed to update message buttons: {e}")


@app.action(re.compile("vote_next_topic_\d+"))
def handle_vote_next_topic(ack, body, client, logger):
    ack()
    user = body.get('user', {})
    user_id = user.get('id')
    user_image = _get_user_image(client, user_id)
    action_id = body['actions'][0]['action_id'] # e.g. vote_next_topic_0

    meta = _extract_meta_from_action(body)
    candidate = meta.get('candidate')

    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'candidate': candidate,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': user_image,
        'vote': 'vote_next_topic'
    }
    record_vote(payload, STATE_DIR)
    logger.info(f"Recorded vote for next topic: {candidate} by {user_id}")

    # Update the UI
    try:
        if body.get('message'):
            blocks = body['message'].get('blocks', [])
            channel_id = body.get('channel', {}).get('id')
            ts = body.get('message', {}).get('ts')

            # Identify which block index was clicked
            clicked_block_idx = -1
            for i, block in enumerate(blocks):
                if block.get('type') == 'section' and block.get('accessory', {}).get('action_id') == action_id:
                    clicked_block_idx = i
                    break

            if clicked_block_idx != -1 and clicked_block_idx + 1 < len(blocks):
                # The next block should be the context block for this candidate
                context_block_idx = clicked_block_idx + 1

                # Use the new votes file structure
                job = meta.get('job') if meta else None
                channel = meta.get('channel') if meta else None
                
                from app.votes import _get_file_path
                votes_file = _get_file_path(STATE_DIR, 'votes', job, channel)
                key = str(meta.get('message_id'))

                count = 0
                recent_images = []

                if os.path.exists(votes_file):
                    with open(votes_file, 'r') as f:
                        data = json.load(f)
                        entry = data.get(key, {})
                        votes = entry.get('votes', [])

                        # Filter for this candidate with correct vote type
                        cand_votes = [v for v in votes if v.get('candidate') == candidate and v.get('vote') == 'vote_next_topic']
                        count = len(cand_votes)

                        seen = set()
                        for v in sorted(cand_votes, key=lambda x: x.get('timestamp', 0), reverse=True):
                            uid = v.get('user_id')
                            img = v.get('user_image')
                            if uid and img and uid not in seen:
                                recent_images.append({'image_url': img, 'alt_text': v.get('user_name', 'User')})
                                seen.add(uid)
                                if len(recent_images) >= 3:
                                    break

                details = {'count': count, 'recent_images': recent_images}
                new_context_block = _make_poll_context_block(details)
                blocks[context_block_idx] = new_context_block

                if channel_id and ts:
                    client.chat_update(channel=channel_id, ts=ts, blocks=blocks)

    except Exception as e:
        logger.error(f"Failed to update candidate votes: {e}")

if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
