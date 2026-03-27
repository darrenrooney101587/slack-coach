import hashlib
import hmac
import json

import pytest

import server


TEST_SECRET = "test-webhook-secret"
TEST_API_KEY = "test-api-key"
TEST_MEETING_ID = "meeting-abc-123"

FULL_TRANSCRIPT = {
    "id": TEST_MEETING_ID,
    "title": "Team Standup",
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

    body = json.dumps({"meetingId": TEST_MEETING_ID, "eventType": "Transcription completed"}).encode()
    resp = _post_with_signature(client, body)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert isinstance(data["blocks"], list)
    assert len(data["blocks"]) > 0


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
