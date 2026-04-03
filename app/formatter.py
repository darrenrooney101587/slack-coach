import re


def _md_to_slack(text: str) -> str:
    return re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)


def _parse_action_items_by_person(raw: str) -> list:
    """
    Returns [(person_name, [items])] if **Name** headers are detected, else [].
    """
    sections = []
    current_person = None
    current_items = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        person_match = re.match(r'^\*{1,2}(.+?)\*{1,2}$', line)
        if person_match:
            if current_person is not None:
                sections.append((current_person, current_items))
            current_person = person_match.group(1).strip()
            current_items = []
        elif current_person is not None:
            item = re.sub(r'^[-•]\s*', '', line).strip()
            if item:
                current_items.append(item)

    if current_person is not None and current_items:
        sections.append((current_person, current_items))

    return sections


def _label_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": f"*{text}*"}}


def format_recap(transcript: dict) -> list:
    title = transcript.get("title") or "Meeting Recap"
    summary = transcript.get("summary") or {}
    overview = summary.get("overview") or summary.get("bullet_gist") or ""
    action_items_raw = summary.get("action_items") or ""

    if isinstance(action_items_raw, list):
        action_items_text = "\n".join(str(a) for a in action_items_raw if a)
    else:
        action_items_text = str(action_items_raw).strip()

    overview = _md_to_slack(overview[:2900])
    action_items_text = _md_to_slack(action_items_text)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
        {"type": "divider"},
    ]

    if overview:
        blocks.append(_label_block("Summary"))
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": overview}})

    if action_items_text:
        blocks.append({"type": "divider"})
        blocks.append(_label_block("Action Items"))

        person_sections = _parse_action_items_by_person(action_items_text)
        if person_sections:
            for person, items in person_sections:
                item_lines = "\n".join(f"• {item}" for item in items)
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{person}*\n{item_lines}"},
                })
        else:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": action_items_text[:2900]},
            })

    blocks.append({"type": "divider"})

    return blocks
