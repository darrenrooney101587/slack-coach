import json
import os

import pytest

from app.review import hold_recap, pop_recap


def test_hold_recap_returns_string_uuid(tmp_path):
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
    recap_id = hold_recap(blocks, "C123", str(tmp_path))
    assert isinstance(recap_id, str)
    assert len(recap_id) == 36


def test_hold_recap_writes_file(tmp_path):
    blocks = [{"type": "section"}]
    recap_id = hold_recap(blocks, "C123", str(tmp_path))
    recap_file = tmp_path / "held_recaps.json"
    assert recap_file.exists()
    data = json.loads(recap_file.read_text())
    assert recap_id in data


def test_hold_recap_stores_blocks_and_channel(tmp_path):
    blocks = [{"type": "section", "text": "Test"}]
    recap_id = hold_recap(blocks, "C999", str(tmp_path))
    data = json.loads((tmp_path / "held_recaps.json").read_text())
    entry = data[recap_id]
    assert entry["blocks"] == blocks
    assert entry["channel_id"] == "C999"
    assert "held_at" in entry
    assert isinstance(entry["held_at"], int)


def test_hold_recap_twice_stores_two_distinct_keys(tmp_path):
    blocks = [{"type": "section"}]
    id1 = hold_recap(blocks, "C1", str(tmp_path))
    id2 = hold_recap(blocks, "C2", str(tmp_path))
    assert id1 != id2
    data = json.loads((tmp_path / "held_recaps.json").read_text())
    assert id1 in data
    assert id2 in data


def test_hold_recap_creates_state_dir(tmp_path):
    new_dir = str(tmp_path / "subdir" / "state")
    hold_recap([], "C1", new_dir)
    assert os.path.isdir(new_dir)


def test_hold_recap_corrupt_json_overwrites_gracefully(tmp_path):
    recap_file = tmp_path / "held_recaps.json"
    recap_file.write_text("not valid json")
    recap_id = hold_recap([{"type": "section"}], "C1", str(tmp_path))
    assert isinstance(recap_id, str)
    data = json.loads(recap_file.read_text())
    assert recap_id in data


def test_pop_recap_returns_entry_and_removes_key(tmp_path):
    blocks = [{"type": "section"}]
    recap_id = hold_recap(blocks, "C123", str(tmp_path))
    entry = pop_recap(recap_id, str(tmp_path))
    assert entry is not None
    assert entry["blocks"] == blocks
    assert entry["channel_id"] == "C123"
    data = json.loads((tmp_path / "held_recaps.json").read_text())
    assert recap_id not in data


def test_pop_recap_unknown_id_returns_none(tmp_path):
    result = pop_recap("nonexistent-id", str(tmp_path))
    assert result is None


def test_pop_recap_unknown_id_no_file_returns_none(tmp_path):
    result = pop_recap("some-id", str(tmp_path / "no_such_dir"))
    assert result is None


def test_pop_recap_idempotent(tmp_path):
    blocks = [{"type": "section"}]
    recap_id = hold_recap(blocks, "C123", str(tmp_path))
    first = pop_recap(recap_id, str(tmp_path))
    second = pop_recap(recap_id, str(tmp_path))
    assert first is not None
    assert second is None
