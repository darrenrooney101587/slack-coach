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


def send_review_dm(
    recap_id: str,
    blocks: list,
    channel_id: str,
    reviewer_user_id: str,
    bot_token: str,
) -> None:
    review_blocks = list(blocks) + [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Review required* — this recap is held for <#{channel_id}>",
            },
        },
        {
            "type": "actions",
            "block_id": "review_actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "recap_approve",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "value": recap_id,
                },
                {
                    "type": "button",
                    "action_id": "recap_skip",
                    "text": {"type": "plain_text", "text": "Skip"},
                    "style": "danger",
                    "value": recap_id,
                },
            ],
        },
    ]
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel": reviewer_user_id,
        "blocks": review_blocks,
        "text": "Recap pending review",
    }
    response = requests.post(SLACK_POST_URL, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack DM failed: {data.get('error')}")
