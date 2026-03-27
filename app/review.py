import json
import os
import time
import uuid


_HELD_RECAPS_FILE = "held_recaps.json"


def _load(state_dir: str) -> dict:
    path = os.path.join(state_dir, _HELD_RECAPS_FILE)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(state_dir: str, data: dict) -> None:
    path = os.path.join(state_dir, _HELD_RECAPS_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def hold_recap(blocks: list, channel_id: str, state_dir: str) -> str:
    os.makedirs(state_dir, exist_ok=True)
    data = _load(state_dir)
    recap_id = str(uuid.uuid4())
    data[recap_id] = {
        "blocks": blocks,
        "channel_id": channel_id,
        "held_at": int(time.time()),
    }
    _save(state_dir, data)
    return recap_id


def pop_recap(recap_id: str, state_dir: str) -> dict | None:
    data = _load(state_dir)
    entry = data.pop(recap_id, None)
    if entry is None:
        return None
    _save(state_dir, data)
    return entry
