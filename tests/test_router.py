import pytest
from router import resolve_channel, load_routing_config


EMAIL_RULE_CONFIG = {
    "default_channel": "CDEFAULT",
    "rules": [
        {
            "match_field": "organizer_email",
            "pattern": "@eng.example.com",
            "channel": "CENG001",
        }
    ],
}

TITLE_RULE_CONFIG = {
    "default_channel": "CDEFAULT",
    "rules": [
        {
            "match_field": "title",
            "pattern": "design review",
            "channel": "CDESIGN1",
        }
    ],
}

MULTI_RULE_CONFIG = {
    "default_channel": "CDEFAULT",
    "rules": [
        {
            "match_field": "organizer_email",
            "pattern": "alice@example.com",
            "channel": "CALICE",
        },
        {
            "match_field": "title",
            "pattern": "planning",
            "channel": "CPLANNING",
        },
    ],
}


def test_organizer_email_match_routes_to_rule_channel():
    transcript = {"organizer_email": "eng-lead@eng.example.com", "title": "Weekly Sync"}
    assert resolve_channel(transcript, EMAIL_RULE_CONFIG) == ["CENG001"]


def test_title_match_routes_to_rule_channel():
    transcript = {"organizer_email": "alice@other.com", "title": "Q2 Design Review"}
    assert resolve_channel(transcript, TITLE_RULE_CONFIG) == ["CDESIGN1"]


def test_title_match_is_case_insensitive():
    transcript = {"organizer_email": "alice@other.com", "title": "DESIGN REVIEW planning"}
    assert resolve_channel(transcript, TITLE_RULE_CONFIG) == ["CDESIGN1"]


def test_no_rule_matches_falls_back_to_default_channel():
    transcript = {"organizer_email": "unknown@other.com", "title": "Random Meeting"}
    assert resolve_channel(transcript, EMAIL_RULE_CONFIG) == ["CDEFAULT"]


def test_empty_rules_list_falls_back_to_default_channel():
    config = {"default_channel": "CDEFAULT", "rules": []}
    transcript = {"organizer_email": "someone@example.com", "title": "Some Meeting"}
    assert resolve_channel(transcript, config) == ["CDEFAULT"]


def test_missing_default_channel_and_no_match_returns_empty_list():
    config = {
        "rules": [
            {
                "match_field": "organizer_email",
                "pattern": "@specific.com",
                "channel": "CSPECIFIC",
            }
        ]
    }
    transcript = {"organizer_email": "user@other.com", "title": "Meeting"}
    assert resolve_channel(transcript, config) == []


def test_first_matching_rule_wins():
    transcript = {"organizer_email": "alice@example.com", "title": "planning session"}
    assert resolve_channel(transcript, MULTI_RULE_CONFIG) == ["CALICE"]


def test_second_rule_matches_when_first_does_not():
    transcript = {"organizer_email": "bob@example.com", "title": "planning session"}
    assert resolve_channel(transcript, MULTI_RULE_CONFIG) == ["CPLANNING"]


def test_missing_transcript_field_does_not_raise():
    transcript = {}
    assert resolve_channel(transcript, EMAIL_RULE_CONFIG) == ["CDEFAULT"]


def test_unknown_match_field_is_skipped():
    config = {
        "default_channel": "CDEFAULT",
        "rules": [
            {
                "match_field": "participants",
                "pattern": "alice@example.com",
                "channel": "CALICE",
            }
        ],
    }
    transcript = {"organizer_email": "alice@example.com", "title": "Meeting"}
    assert resolve_channel(transcript, config) == ["CDEFAULT"]


def test_channels_list_rule_returns_all_targets():
    config = {
        "default_channel": "CDEFAULT",
        "rules": [
            {
                "match_field": "title",
                "pattern": "WingSwept",
                "channels": ["U074ZR6DJKZ", "U0327158VA8"],
            }
        ],
    }
    transcript = {"title": "WingSwept Discussion | Darren <> Pavlo"}
    assert resolve_channel(transcript, config) == ["U074ZR6DJKZ", "U0327158VA8"]


def test_load_routing_config_reads_yaml_file(tmp_path):
    config_file = tmp_path / "routing.yml"
    config_file.write_text(
        "default_channel: CTEST\nrules:\n  - match_field: title\n    pattern: test\n    channel: CTEST1\n"
    )
    config = load_routing_config(str(config_file))
    assert config["default_channel"] == "CTEST"
    assert config["rules"][0]["channel"] == "CTEST1"


def test_load_routing_config_raises_file_not_found_for_missing_path():
    with pytest.raises(FileNotFoundError):
        load_routing_config("/nonexistent/path/routing.yml")
