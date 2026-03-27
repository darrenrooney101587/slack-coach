import hashlib
import hmac
import json

import pytest

import server
from slack import post_recap


TEST_SECRET = "test-webhook-secret"
TEST_API_KEY = "test-api-key"
TEST_MEETING_ID = "meeting-abc-123"

FULL_TRANSCRIPT = {
    "id": TEST_MEETING_ID,
    "title": "Team Standup",
    "organizer_email": "alice@example.com",
    "transcript_url": "https://app.fireflies.ai/view/meeting-abc-123",
    "participants": ["alice@example.com", "bob@example.com"],
    "summary": {
        "overview": "We discussed sprint goals.",
        "bullet_gist": "- Sprint goals discussed",
        "action_items": "- Alice to complete PR by Friday",
    },
}


def _make_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "FIREFLIES_WEBHOOK_SECRET", TEST_SECRET)
    monkeypatch.setattr(server, "FIREFLIES_API_KEY", TEST_API_KEY)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def _post_with_signature(client, body: bytes, secret: str = TEST_SECRET, event_type: str = "Transcription completed", meeting_id: str = TEST_MEETING_ID):
    sig = _make_signature(secret, body)
    return client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
        headers={"x-hub-signature": sig},
    )


def test_valid_transcription_completed_returns_200_with_blocks(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {"default_channel": "CTEST001", "rules": []})
    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", "xoxb-test")
    calls = []
    monkeypatch.setattr(server, "post_recap", lambda blocks, channel, token: calls.append((blocks, channel, token)))

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_invalid_signature_returns_403(client):
    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
        headers={"x-hub-signature": "wrongsignature"},
    )

    assert resp.status_code == 403


def test_missing_signature_header_returns_403(client):
    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
    )

    assert resp.status_code == 403


def test_malformed_json_returns_400(client, monkeypatch):
    monkeypatch.setattr(server, "FIREFLIES_WEBHOOK_SECRET", "")

    body = b"not-json"
    resp = client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_json"


def test_missing_meeting_id_returns_400(client):
    body = json.dumps({"eventType": "Transcription completed"}).encode()
    sig = _make_signature(TEST_SECRET, body)
    resp = client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
        headers={"x-hub-signature": sig},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "missing_meetingId"


def test_unrecognized_event_type_returns_200_skipped(client):
    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "some_future_event"}).encode()
    sig = _make_signature(TEST_SECRET, body)
    resp = client.post(
        "/webhooks/fireflies",
        data=body,
        content_type="application/json",
        headers={"x-hub-signature": sig},
    )

    assert resp.status_code == 200
    assert resp.get_json()["skipped"] is True


def test_graphql_response_missing_required_fields_returns_422(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: {})

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 422
    assert resp.get_json()["error"] == "missing_required_fields"


def test_no_signature_verification_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(server, "FIREFLIES_WEBHOOK_SECRET", None)
    monkeypatch.setattr(server, "FIREFLIES_API_KEY", TEST_API_KEY)
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: {})
    server.app.config["TESTING"] = True

    with server.app.test_client() as c:
        body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
        resp = c.post(
            "/webhooks/fireflies",
            data=body,
            content_type="application/json",
        )

    assert resp.status_code != 403


def test_webhook_posts_to_slack_and_returns_200(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {"default_channel": "CTEST001", "rules": []})
    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", "xoxb-test")
    calls = []
    monkeypatch.setattr(server, "post_recap", lambda blocks, channel, token: calls.append((blocks, channel, token)))

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert len(calls) == 1
    assert calls[0][1] == "CTEST001"


def test_webhook_no_routing_target_returns_500(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {})

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "no_routing_target"


def test_webhook_no_bot_token_returns_500(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {"default_channel": "CTEST001", "rules": []})
    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", None)

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "no_bot_token"


def test_webhook_not_in_channel_returns_403(client, monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {"default_channel": "CTEST001", "rules": []})
    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setattr(server, "post_recap", lambda blocks, channel, token: (_ for _ in ()).throw(RuntimeError("Slack API error: not_in_channel")))

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 403
    data = resp.get_json()
    assert data["error"] == "bot_not_in_channel"


def _setup_review_common(monkeypatch):
    monkeypatch.setattr(server, "fetch_transcript", lambda mid, key: FULL_TRANSCRIPT)
    monkeypatch.setattr(server, "_get_routing_config", lambda: {"default_channel": "CTEST001", "rules": []})
    monkeypatch.setattr(server, "SLACK_BOT_TOKEN", "xoxb-test")


def test_review_mode_holds_recap_and_returns_held(client, monkeypatch):
    _setup_review_common(monkeypatch)
    monkeypatch.setattr(server, "REVIEW_MODE", True)
    monkeypatch.setattr(server, "REVIEWER_USER_ID", "U999")

    from unittest.mock import MagicMock
    mock_hold = MagicMock(return_value="recap-abc")
    mock_send_dm = MagicMock(return_value=None)
    mock_post = MagicMock()
    monkeypatch.setattr(server, "hold_recap", mock_hold)
    monkeypatch.setattr(server, "send_review_dm", mock_send_dm)
    monkeypatch.setattr(server, "post_recap", mock_post)

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["held"] is True
    assert data["recap_id"] == "recap-abc"
    mock_post.assert_not_called()
    mock_hold.assert_called_once()
    mock_send_dm.assert_called_once()
    assert mock_send_dm.call_args[1].get("reviewer_user_id") == "U999" or mock_send_dm.call_args[0][3] == "U999"
    assert mock_send_dm.call_args[1].get("recap_id") == "recap-abc" or mock_send_dm.call_args[0][0] == "recap-abc"


def test_review_mode_missing_reviewer_returns_500(client, monkeypatch):
    _setup_review_common(monkeypatch)
    monkeypatch.setattr(server, "REVIEW_MODE", True)
    monkeypatch.setattr(server, "REVIEWER_USER_ID", "")

    from unittest.mock import MagicMock
    mock_hold = MagicMock()
    monkeypatch.setattr(server, "hold_recap", mock_hold)

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "no_reviewer_configured"
    mock_hold.assert_not_called()


def test_review_mode_dm_failure_returns_500(client, monkeypatch):
    _setup_review_common(monkeypatch)
    monkeypatch.setattr(server, "REVIEW_MODE", True)
    monkeypatch.setattr(server, "REVIEWER_USER_ID", "U999")

    from unittest.mock import MagicMock
    monkeypatch.setattr(server, "hold_recap", MagicMock(return_value="recap-xyz"))
    monkeypatch.setattr(server, "send_review_dm", MagicMock(side_effect=RuntimeError("dm_failed")))

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "reviewer_dm_failed"


def test_review_mode_false_posts_directly(client, monkeypatch):
    _setup_review_common(monkeypatch)
    monkeypatch.setattr(server, "REVIEW_MODE", False)

    from unittest.mock import MagicMock
    mock_post = MagicMock(return_value=None)
    mock_hold = MagicMock()
    monkeypatch.setattr(server, "post_recap", mock_post)
    monkeypatch.setattr(server, "hold_recap", mock_hold)

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "held" not in data
    mock_post.assert_called_once()
    mock_hold.assert_not_called()
