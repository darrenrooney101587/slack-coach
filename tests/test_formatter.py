from app.formatter import format_recap


def _mrkdwn_blocks(blocks):
    return [b for b in blocks if b.get("type") == "section" and b.get("text", {}).get("type") == "mrkdwn"]


def test_empty_dict_returns_list_without_error():
    result = format_recap({})
    assert isinstance(result, list)
    assert len(result) >= 2


def test_full_transcript_contains_all_sections():
    transcript = {
        "title": "My Meeting",
        "transcript_url": "https://example.com",
        "summary": {
            "overview": "Lots happened",
            "action_items": ["Do A", "Do B"],
        },
    }
    blocks = format_recap(transcript)

    header_blocks = [b for b in blocks if b.get("type") == "header"]
    assert header_blocks, "expected a header block"
    assert header_blocks[0]["text"]["text"] == "My Meeting"

    mrkdwn_texts = [b["text"]["text"] for b in _mrkdwn_blocks(blocks)]
    assert any("Summary" in t for t in mrkdwn_texts)
    assert any("Action Items" in t for t in mrkdwn_texts)
    assert any("- Do A" in t for t in mrkdwn_texts)
    assert any("- Do B" in t for t in mrkdwn_texts)
    assert any("example.com" in t for t in mrkdwn_texts)


def test_action_items_as_string_preserved():
    transcript = {"summary": {"action_items": "First item\nSecond item"}}
    blocks = format_recap(transcript)

    action_blocks = [b["text"]["text"] for b in _mrkdwn_blocks(blocks) if "Action Items" in b["text"]["text"]]
    assert action_blocks, "expected an Action Items block"
    combined = "\n".join(action_blocks)
    assert "First item" in combined
    assert "Second item" in combined


def test_null_action_items_omitted():
    transcript = {"summary": {"action_items": None}}
    blocks = format_recap(transcript)

    mrkdwn_texts = [b["text"]["text"] for b in _mrkdwn_blocks(blocks)]
    assert not any("Action Items" in t for t in mrkdwn_texts)


def test_long_overview_truncated():
    transcript = {"summary": {"overview": "x" * 3000}}
    blocks = format_recap(transcript)

    summary_blocks = [b for b in _mrkdwn_blocks(blocks) if "Summary" in b["text"]["text"]]
    assert summary_blocks, "expected a Summary block"
    assert len(summary_blocks[0]["text"]["text"]) <= 3000


def test_missing_transcript_url_omits_link_section():
    transcript = {"summary": {"overview": "Some notes"}}
    blocks = format_recap(transcript)

    mrkdwn_texts = [b["text"]["text"] for b in _mrkdwn_blocks(blocks)]
    assert not any("|View full transcript>" in t for t in mrkdwn_texts)


def test_empty_transcript_url_omits_link_section():
    transcript = {"transcript_url": "", "summary": {"overview": "Some notes"}}
    blocks = format_recap(transcript)

    mrkdwn_texts = [b["text"]["text"] for b in _mrkdwn_blocks(blocks)]
    assert not any("|View full transcript>" in t for t in mrkdwn_texts)


def test_long_title_truncated_in_header():
    transcript = {"title": "A" * 200}
    blocks = format_recap(transcript)

    header_blocks = [b for b in blocks if b.get("type") == "header"]
    assert header_blocks, "expected a header block"
    assert len(header_blocks[0]["text"]["text"]) <= 150


def test_missing_title_uses_fallback():
    blocks = format_recap({})

    header_blocks = [b for b in blocks if b.get("type") == "header"]
    assert header_blocks, "expected a header block"
    assert header_blocks[0]["text"]["text"] == "Meeting Recap"
