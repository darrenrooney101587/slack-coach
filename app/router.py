import logging
import re

import yaml

logger = logging.getLogger(__name__)


def load_routing_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def resolve_channel(transcript: dict, config: dict) -> list[str]:
    rules = config.get("rules", [])
    for rule in rules:
        field = rule.get("match_field", "")
        pattern = rule.get("pattern", "")

        value = ""
        if field == "title":
            value = transcript.get("title") or ""
        elif field == "organizer_email":
            value = transcript.get("organizer_email") or ""

        if not value:
            logger.info("resolve_channel: rule skipped field=%r pattern=%r reason=field_empty_or_missing", field, pattern)
            continue

        matched = bool(pattern and re.search(pattern, value, re.IGNORECASE))
        logger.info("resolve_channel: rule evaluated field=%r pattern=%r value=%r matched=%s", field, pattern, value, matched)

        if matched:
            channels = rule.get("channels") or [rule["channel"]]
            logger.info("resolve_channel: rule matched returning channels=%r", channels)
            return channels

    default = config.get("default_channel", "")
    logger.info("resolve_channel: no rules matched, using default_channel=%r", default)
    return [default] if default else []
