def format_recap(transcript: dict) -> list:
    title = transcript.get("title") or "Meeting Recap"
    transcript_url = transcript.get("transcript_url", "")
    summary = transcript.get("summary") or {}
    overview = summary.get("overview") or summary.get("bullet_gist") or ""
    action_items_raw = summary.get("action_items") or ""

    if isinstance(action_items_raw, list):
        action_items_text = "\n".join(f"- {a}" for a in action_items_raw if a)
    else:
        action_items_text = str(action_items_raw).strip()

    overview = overview[:2900]
    action_items_text = action_items_text[:2900]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
        {"type": "divider"},
    ]

    if overview:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary*\n{overview}"},
        })

    if action_items_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Action Items*\n{action_items_text}"},
        })

    blocks.append({"type": "divider"})

    if transcript_url:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<{transcript_url}|View full transcript>"},
        })

    return blocks
