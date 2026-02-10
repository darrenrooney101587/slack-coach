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
    """Fetch user image with error handling and timeout."""
    try:
        resp = client.users_info(user=user_id)
        if resp.get('ok'):
            return resp['user']['profile'].get('image_48')  # 48x48 is standard for context blocks
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
    # Acknowledge immediately to prevent timeout
    ack()
    
    user = body.get('user', {})
    user_id = user.get('id')
    
    # Extract metadata first (fast operation)
    meta = _extract_meta_from_action(body)
    
    # Record vote immediately (don't wait for user image)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': None,  # Will be fetched separately
        'vote': 'thumbs_up'
    }
    
    try:
        record_vote(payload, STATE_DIR)
        logger.info(f"Recorded thumbs_up from user {user_id}")
    except Exception as e:
        logger.error(f"Failed to record thumbs_up: {e}")
        return  # Exit early if we can't record the vote
    
    # Fetch user image asynchronously (non-critical)
    user_image = _get_user_image(client, user_id)
    if user_image:
        # Update the vote record with user image
        payload['user_image'] = user_image
        try:
            record_vote(payload, STATE_DIR)
        except Exception as e:
            logger.warning(f"Failed to update vote with user_image: {e}")

    # Update the button UI to show acknowledgement
    try:
        if body.get('message'):
            blocks = body['message'].get('blocks', [])
            # Find the actions block at the end (usually last block or second to last)
            for block in reversed(blocks):
                if block['type'] == 'actions':
                    for element in block.get('elements', []):
                        if element.get('action_id') == 'thumbs_up':
                            element['text']['text'] = 'Helpful   ✓'
                        elif element.get('action_id') == 'thumbs_down':
                            element['text']['text'] = 'Not Helpful   👎'

                    # Update the message
                    channel_id = body.get('channel', {}).get('id')
                    ts = body.get('message', {}).get('ts')
                    if channel_id and ts:
                        client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
                        logger.info(f"Updated button UI for message {ts}")
                    break
    except Exception as e:
        logger.error(f"Failed to update message buttons: {e}", exc_info=True)

@app.action('thumbs_down')
def handle_thumbs_down(ack, body, client, logger):
    # Acknowledge immediately to prevent timeout
    ack()
    
    user = body.get('user', {})
    user_id = user.get('id')
    
    # Extract metadata first (fast operation)
    meta = _extract_meta_from_action(body)
    
    # Record vote immediately (don't wait for user image)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': None,  # Will be fetched separately
        'vote': 'thumbs_down'
    }
    
    try:
        record_vote(payload, STATE_DIR)
        logger.info(f"Recorded thumbs_down from user {user_id}")
    except Exception as e:
        logger.error(f"Failed to record thumbs_down: {e}")
        return  # Exit early if we can't record the vote
    
    # Fetch user image asynchronously (non-critical)
    user_image = _get_user_image(client, user_id)
    if user_image:
        # Update the vote record with user image
        payload['user_image'] = user_image
        try:
            record_vote(payload, STATE_DIR)
        except Exception as e:
            logger.warning(f"Failed to update vote with user_image: {e}")

    # Update the button UI to show acknowledgement
    try:
        if body.get('message'):
            blocks = body['message'].get('blocks', [])
            for block in reversed(blocks):
                if block['type'] == 'actions':
                    for element in block.get('elements', []):
                        if element.get('action_id') == 'thumbs_down':
                            element['text']['text'] = 'Not Helpful   ✓'
                        elif element.get('action_id') == 'thumbs_up':
                            element['text']['text'] = 'Helpful   👍'

                    channel_id = body.get('channel', {}).get('id')
                    ts = body.get('message', {}).get('ts')
                    if channel_id and ts:
                        client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
                        logger.info(f"Updated button UI for message {ts}")
                    break
    except Exception as e:
        logger.error(f"Failed to update message buttons: {e}", exc_info=True)

@app.action(re.compile("vote_next_topic_\d+"))
def handle_vote_next_topic(ack, body, client, logger):
    # Acknowledge immediately to prevent timeout
    ack()
    
    user = body.get('user', {})
    user_id = user.get('id')
    action_id = body['actions'][0]['action_id']  # e.g. vote_next_topic_0

    meta = _extract_meta_from_action(body)
    candidate = meta.get('candidate') if meta else None

    # Record vote immediately (don't wait for user image)
    payload = {
        'message_id': meta.get('message_id') if meta else None,
        'topic': meta.get('topic') if meta else None,
        'job': meta.get('job') if meta else None,
        'channel': meta.get('channel') if meta else None,
        'date': meta.get('date') if meta else None,
        'candidate': candidate,
        'user_id': user_id,
        'user_name': user.get('username') or user.get('name'),
        'user_image': None,  # Will be fetched separately
        'vote': 'vote_next_topic'
    }
    
    try:
        record_vote(payload, STATE_DIR)
        logger.info(f"Recorded vote for next topic: {candidate} by {user_id}")
    except Exception as e:
        logger.error(f"Failed to record vote: {e}")
        return  # Exit early if we can't record the vote
    
    # Fetch user image asynchronously (non-critical)
    user_image = _get_user_image(client, user_id)
    if user_image:
        payload['user_image'] = user_image
        try:
            record_vote(payload, STATE_DIR)
        except Exception as e:
            logger.warning(f"Failed to update vote with user_image: {e}")

    # Update the UI to show vote counts for all candidates
    try:
        if not body.get('message'):
            logger.warning("No message in body, skipping UI update")
            return

        blocks = body['message'].get('blocks', [])
        channel_id = body.get('channel', {}).get('id')
        ts = body.get('message', {}).get('ts')

        if not (channel_id and ts):
            logger.warning("Missing channel_id or ts, skipping UI update")
            return

        # Find all candidate section blocks and corresponding context block indices
        candidates = []
        cand_context_indices = {}
        import re as _re
        for i, block in enumerate(blocks):
            if block.get('type') == 'section':
                accessory = block.get('accessory') or {}
                action_id_val = accessory.get('action_id', '')
                if isinstance(action_id_val, str) and action_id_val.startswith('vote_next_topic_'):
                    # Extract candidate text from the section
                    text_obj = block.get('text') or {}
                    cand_text = text_obj.get('text', '').strip()
                    # Remove surrounding asterisks/bolding if present
                    cand_clean = _re.sub(r"^\*+|\*+$", '', cand_text).strip()
                    candidates.append(cand_clean)
                    ctx_idx = i + 1
                    if ctx_idx < len(blocks) and blocks[ctx_idx].get('type') == 'context':
                        cand_context_indices[cand_clean] = ctx_idx

        if not candidates:
            logger.info("No candidates found in message blocks; skipping UI refresh")
            return

        # Compute poll details for all candidates
        job = meta.get('job') if meta else None
        channel = meta.get('channel') if meta else None
        key = str(meta.get('message_id')) if meta else None

        poll_details = get_poll_details(key, candidates, STATE_DIR, job, channel)

        # Replace each candidate's context block with fresh details
        for cand in candidates:
            details = poll_details.get(cand) if poll_details and isinstance(poll_details, dict) else None
            if not details:
                details = {'count': 0, 'recent_images': []}
            ctx_idx = cand_context_indices.get(cand)
            if ctx_idx is not None and ctx_idx < len(blocks):
                blocks[ctx_idx] = _make_poll_context_block(details)

        # Single chat_update to refresh the whole poll UI
        client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
        logger.info(f"Refreshed poll UI for message {ts}")

    except Exception as e:
        logger.error(f"Failed to update candidate votes: {e}", exc_info=True)

if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
