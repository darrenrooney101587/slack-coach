import pytest
import requests

from slack import post_recap


BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test recap"}}]
CHANNEL_ID = "C0123456789"
BOT_TOKEN = "xoxb-test-token"


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
