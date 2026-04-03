from app.formatter import format_recap, _parse_action_items_by_person, _md_to_slack


def _mrkdwn_blocks(blocks):
    return [b for b in blocks if b.get("type") == "section" and b.get("text", {}).get("type") == "mrkdwn"]


def _all_mrkdwn_texts(blocks):
    return [b["text"]["text"] for b in _mrkdwn_blocks(blocks)]


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
    assert header_blocks
    assert header_blocks[0]["text"]["text"] == "My Meeting"

    texts = _all_mrkdwn_texts(blocks)
    assert any("Summary" in t for t in texts)
    assert any("Action Items" in t for t in texts)
    assert any("Do A" in t for t in texts)
    assert any("Do B" in t for t in texts)


def test_action_items_as_string_preserved():
    transcript = {"summary": {"action_items": "First item\nSecond item"}}
    blocks = format_recap(transcript)

    texts = _all_mrkdwn_texts(blocks)
    assert any("Action Items" in t for t in texts)
    assert any("First item" in t for t in texts)
    assert any("Second item" in t for t in texts)


def test_null_action_items_omitted():
    transcript = {"summary": {"action_items": None}}
    blocks = format_recap(transcript)

    texts = _all_mrkdwn_texts(blocks)
    assert not any("Action Items" in t for t in texts)


def test_long_overview_truncated():
    transcript = {"summary": {"overview": "x" * 3000}}
    blocks = format_recap(transcript)

    texts = _all_mrkdwn_texts(blocks)
    assert any("Summary" in t for t in texts)
    assert all(len(t) <= 3000 for t in texts)



def test_long_title_truncated_in_header():
    transcript = {"title": "A" * 200}
    blocks = format_recap(transcript)

    header_blocks = [b for b in blocks if b.get("type") == "header"]
    assert header_blocks
    assert len(header_blocks[0]["text"]["text"]) <= 150


def test_missing_title_uses_fallback():
    blocks = format_recap({})

    header_blocks = [b for b in blocks if b.get("type") == "header"]
    assert header_blocks
    assert header_blocks[0]["text"]["text"] == "Meeting Recap"


def test_action_items_parsed_by_person():
    raw = "**Darren Rooney**\nDo the thing\nAnother task\n\n**Derek Scott**\nReview PR\nWrite tests"
    transcript = {"summary": {"action_items": raw}}
    blocks = format_recap(transcript)

    texts = _all_mrkdwn_texts(blocks)
    darren_block = next((t for t in texts if "Darren Rooney" in t), None)
    derek_block = next((t for t in texts if "Derek Scott" in t), None)

    assert darren_block is not None
    assert "• Do the thing" in darren_block
    assert "• Another task" in darren_block

    assert derek_block is not None
    assert "• Review PR" in derek_block
    assert "• Write tests" in derek_block


def test_action_items_without_person_headers_renders_flat():
    transcript = {"summary": {"action_items": "Task one\nTask two\nTask three"}}
    blocks = format_recap(transcript)

    texts = _all_mrkdwn_texts(blocks)
    flat_block = next((t for t in texts if "Task one" in t), None)
    assert flat_block is not None
    assert "Task two" in flat_block


def test_markdown_bold_converted_to_slack_bold():
    assert _md_to_slack("**hello**") == "*hello*"
    assert _md_to_slack("**CICD Workflow:** text") == "*CICD Workflow:* text"
    assert _md_to_slack("no bold here") == "no bold here"


def test_parse_action_items_by_person_returns_pairs():
    raw = "**Alice**\nItem 1\nItem 2\n\n**Bob**\nItem 3"
    result = _parse_action_items_by_person(raw)
    assert result == [("Alice", ["Item 1", "Item 2"]), ("Bob", ["Item 3"])]


def test_parse_action_items_no_headers_returns_empty():
    raw = "Just a plain item\nAnother item"
    result = _parse_action_items_by_person(raw)
    assert result == []
