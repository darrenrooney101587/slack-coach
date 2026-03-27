import pytest
import requests

from slack import post_recap, send_review_dm


BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test recap"}}]
CHANNEL_ID = "C0123456789"
BOT_TOKEN = "xoxb-test-token"
REVIEWER_USER_ID = "U456"


def _mock_response(mocker, json_data, raise_http_error=False):
    mock_resp = mocker.MagicMock()
    if raise_http_error:
        mock_resp.raise_for_status.side_effect = requests.HTTPError("HTTP error")
    else:
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = json_data
    return mock_resp


def test_post_recap_calls_correct_url(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)

    mock_post.assert_called_once()
    args, _ = mock_post.call_args
    assert args[0] == "https://slack.com/api/chat.postMessage"


def test_post_recap_sends_channel_and_blocks(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["channel"] == CHANNEL_ID
    assert kwargs["json"]["blocks"] == BLOCKS


def test_post_recap_ok_response_does_not_raise(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True, "ts": "123"}))

    post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)


def test_post_recap_error_response_raises_runtime_error(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": False, "error": "channel_not_found"}))

    with pytest.raises(RuntimeError, match="channel_not_found"):
        post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)


def test_post_recap_not_in_channel_raises_runtime_error(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": False, "error": "not_in_channel"}))

    with pytest.raises(RuntimeError, match="not_in_channel"):
        post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)


def test_post_recap_http_error_raises(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, None, raise_http_error=True))

    with pytest.raises(requests.HTTPError):
        post_recap(BLOCKS, CHANNEL_ID, BOT_TOKEN)


def test_send_review_dm_calls_correct_url(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)

    mock_post.assert_called_once()
    args, _ = mock_post.call_args
    assert args[0] == "https://slack.com/api/chat.postMessage"


def test_send_review_dm_sends_to_reviewer_user_id(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["channel"] == REVIEWER_USER_ID


def test_send_review_dm_includes_recap_blocks(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)

    _, kwargs = mock_post.call_args
    sent_blocks = kwargs["json"]["blocks"]
    for block in BLOCKS:
        assert block in sent_blocks


def test_send_review_dm_includes_approve_skip_buttons(mocker):
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)

    _, kwargs = mock_post.call_args
    sent_blocks = kwargs["json"]["blocks"]
    all_elements = [
        element
        for block in sent_blocks
        for element in block.get("elements", [])
    ]
    action_ids = {el["action_id"] for el in all_elements if "action_id" in el}
    assert "recap_approve" in action_ids
    assert "recap_skip" in action_ids


def test_send_review_dm_button_values_carry_recap_id(mocker):
    recap_id = "test-recap-123"
    mock_post = mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": True}))

    send_review_dm(recap_id, BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)

    _, kwargs = mock_post.call_args
    sent_blocks = kwargs["json"]["blocks"]
    all_elements = [
        element
        for block in sent_blocks
        for element in block.get("elements", [])
    ]
    button_values = {el["value"] for el in all_elements if el.get("type") == "button"}
    assert all(v == recap_id for v in button_values)


def test_send_review_dm_ok_false_raises_runtime_error(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, {"ok": False, "error": "not_in_channel"}))

    with pytest.raises(RuntimeError, match="not_in_channel"):
        send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)


def test_send_review_dm_http_error_raises(mocker):
    mocker.patch("slack.requests.post", return_value=_mock_response(mocker, None, raise_http_error=True))

    with pytest.raises(requests.HTTPError):
        send_review_dm("rid", BLOCKS, CHANNEL_ID, REVIEWER_USER_ID, BOT_TOKEN)
