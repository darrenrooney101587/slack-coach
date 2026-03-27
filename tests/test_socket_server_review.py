import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test")

import slack_bolt as _bolt
_orig_bolt_init = _bolt.App.__init__


def _bolt_init_no_verify(self, *args, **kwargs):
    kwargs["token_verification_enabled"] = False
    _orig_bolt_init(self, *args, **kwargs)


_bolt.App.__init__ = _bolt_init_no_verify

for _key in [k for k in sys.modules if k in ("app.socket_server", "socket_server")]:
    del sys.modules[_key]

from app.socket_server import handle_recap_approve, handle_recap_skip


def make_body(recap_id):
    return {
        "actions": [{"value": recap_id}],
        "channel": {"id": "C-dm"},
        "message": {"ts": "111.222"},
    }


def test_recap_approve_posts_and_updates_dm():
    mock_client = MagicMock()
    entry = {"blocks": [{"type": "section"}], "channel_id": "C-main"}

    with patch("app.socket_server.pop_recap", return_value=entry) as mock_pop, \
         patch("app.socket_server.post_recap", return_value=None) as mock_post:
        handle_recap_approve(
            ack=MagicMock(),
            body=make_body("rid-1"),
            client=mock_client,
            logger=MagicMock(),
        )
        mock_pop.assert_called_once()
        assert mock_pop.call_args[0][0] == "rid-1"
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == [{"type": "section"}]
        assert mock_post.call_args[0][1] == "C-main"
        mock_client.chat_update.assert_called_once()
        call_kwargs = mock_client.chat_update.call_args[1]
        assert call_kwargs["channel"] == "C-dm"
        assert call_kwargs["ts"] == "111.222"
        assert "Approved" in call_kwargs["text"]


def test_recap_skip_discards_and_updates_dm():
    mock_client = MagicMock()

    with patch("app.socket_server.pop_recap", return_value=None) as mock_pop, \
         patch("app.socket_server.post_recap") as mock_post:
        ack = MagicMock()
        handle_recap_skip(
            ack=ack,
            body=make_body("rid-2"),
            client=mock_client,
            logger=MagicMock(),
        )
        ack.assert_called_once()
        mock_pop.assert_called_once()
        assert mock_pop.call_args[0][0] == "rid-2"
        mock_post.assert_not_called()
        mock_client.chat_update.assert_called_once()
        call_kwargs = mock_client.chat_update.call_args[1]
        assert "Skipped" in call_kwargs["text"]


def test_recap_approve_idempotent_when_recap_missing():
    mock_client = MagicMock()
    mock_logger = MagicMock()

    with patch("app.socket_server.pop_recap", return_value=None), \
         patch("app.socket_server.post_recap") as mock_post:
        ack = MagicMock()
        handle_recap_approve(
            ack=ack,
            body=make_body("rid-3"),
            client=mock_client,
            logger=mock_logger,
        )
        ack.assert_called_once()
        mock_post.assert_not_called()
        mock_logger.warning.assert_called_once()
        mock_client.chat_update.assert_not_called()
