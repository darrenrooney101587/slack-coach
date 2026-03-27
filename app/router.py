import re

import yaml


def load_routing_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def resolve_channel(transcript: dict, config: dict) -> str:
    rules = config.get("rules", [])
    for rule in rules:
        field = rule.get("match_field", "")
        pattern = rule.get("pattern", "")
        channel = rule.get("channel", "")

        value = ""
        if field == "title":
            value = transcript.get("title") or ""
        elif field == "organizer_email":
            value = transcript.get("organizer_email") or ""

        if pattern and value and re.search(pattern, value, re.IGNORECASE):
            return channel

    return config.get("default_channel", "")
