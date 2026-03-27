import requests

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"


def post_recap(blocks: list, channel_id: str, bot_token: str) -> None:
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel": channel_id,
        "blocks": blocks,
        "text": "Meeting Recap",
    }
    response = requests.post(SLACK_POST_URL, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error')}")
