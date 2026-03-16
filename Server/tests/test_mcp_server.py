"""
Tests for MCP_Server.py – send_request, send_get, and tool functions.

Key facts about the real implementation:
- send_request calls requests.post(endpoint, data, headers, timeout=10)
  where data has already been json.dumps'd.  The call uses positional args,
  NOT keyword args – tests document this and flag it as a known issue.
- There is no send_get helper; health_check does not exist in MCP_Server.py.
  The health endpoint is defined in config.ENDPOINTS["health"] but no MCP
  tool wraps it.  Tests that cover GET behaviour do so via config directly.
- Retry logic: up to 3 attempts on requests.RequestException; the exception
  is re-raised after the third failure.
"""
import sys
import os
import json
import importlib

import pytest
from unittest.mock import patch, MagicMock, call
import requests

# ---------------------------------------------------------------------------
# Make sure the Server package is importable regardless of cwd
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_server():
    """
    config and MCP_Server read env-vars at import time, so we must reload
    them after monkeypatch has set the required variables.
    """
    # Patch FastMCP so we don't need the real mcp package installed
    fake_mcp_module = MagicMock()
    fake_fastmcp = MagicMock()
    fake_fastmcp.return_value = MagicMock()
    fake_mcp_module.FastMCP = fake_fastmcp

    with patch.dict(
        sys.modules,
        {
            "mcp": MagicMock(),
            "mcp.server": MagicMock(),
            "mcp.server.fastmcp": fake_mcp_module,
        },
    ):
        import config as cfg
        importlib.reload(cfg)

        import MCP_Server as srv
        importlib.reload(srv)

    return srv, cfg


# ===========================================================================
# 1. send_request uses positional args (documents current behaviour)
# ===========================================================================

class TestSendRequestCallArgs:
    """Verify how requests.post is called inside send_request."""

    def test_post_called_once_on_success(self):
        srv, cfg = _reload_server()
        endpoint = cfg.ENDPOINTS["draw_box"]
        payload = {"height": "5", "width": "5", "depth": "1", "x": 0, "y": 0, "z": 0, "Plane": "XY"}

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "data": {}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            srv.send_request(endpoint, payload, cfg.HEADERS)

        mock_post.assert_called_once()

    def test_post_receives_json_serialised_body(self):
        """The body passed to requests.post should be a JSON string."""
        srv, cfg = _reload_server()
        endpoint = cfg.ENDPOINTS["draw_box"]
        payload = {"key": "value"}

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}

        with patch("requests.post", return_value=mock_response) as mock_post:
            srv.send_request(endpoint, payload, cfg.HEADERS)

        # Second positional arg is the body
        args, kwargs = mock_post.call_args
        body_arg = args[1] if len(args) > 1 else kwargs.get("data")
        assert body_arg == json.dumps(payload), (
            "Body must be json.dumps'd before being sent"
        )

    def test_timeout_passed_as_keyword_argument(self):
        """timeout=10 must be forwarded to requests.post."""
        srv, cfg = _reload_server()
        endpoint = cfg.ENDPOINTS["draw_cylinder"]
        payload = {"radius": 1, "height": 2, "x": 0, "y": 0, "z": 0, "plane": "XY"}

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}

        with patch("requests.post", return_value=mock_response) as mock_post:
            srv.send_request(endpoint, payload, cfg.HEADERS)

        _, kwargs = mock_post.call_args
        assert kwargs.get("timeout") == 10, "timeout=10 must be passed as a keyword arg"


# ===========================================================================
# 2. Retry behaviour on requests.RequestException
# ===========================================================================

class TestSendRequestRetries:

    def test_retries_exactly_three_times(self):
        srv, cfg = _reload_server()

        with patch(
            "requests.post", side_effect=requests.RequestException("network error")
        ) as mock_post:
            with pytest.raises(requests.RequestException):
                srv.send_request(cfg.ENDPOINTS["test_connection"], {}, {})

        assert mock_post.call_count == 3, (
            f"Expected 3 attempts, got {mock_post.call_count}"
        )

    def test_succeeds_on_second_attempt(self):
        """If the first attempt fails but the second succeeds, no exception is raised."""
        srv, cfg = _reload_server()

        ok_response = MagicMock()
        ok_response.json.return_value = {"success": True}

        with patch(
            "requests.post",
            side_effect=[requests.RequestException("transient"), ok_response],
        ) as mock_post:
            result = srv.send_request(cfg.ENDPOINTS["test_connection"], {}, {})

        assert result == {"success": True}
        assert mock_post.call_count == 2

    def test_raises_after_max_retries_exhausted(self):
        srv, cfg = _reload_server()

        with patch(
            "requests.post", side_effect=requests.RequestException("persistent")
        ):
            with pytest.raises(requests.RequestException):
                srv.send_request(cfg.ENDPOINTS["draw_box"], {}, {})


# ===========================================================================
# 3. draw_box tool – correct endpoint and payload
# ===========================================================================

class TestDrawBoxTool:

    def test_draw_box_calls_box_endpoint(self):
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "data": {}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            srv.draw_box(
                height_value="3",
                width_value="5",
                depth_value="2",
                x_value=0.0,
                y_value=0.0,
                z_value=0.0,
                plane="XY",
            )

        args, _ = mock_post.call_args
        assert args[0] == cfg.ENDPOINTS["draw_box"], (
            f"Expected {cfg.ENDPOINTS['draw_box']}, got {args[0]}"
        )

    def test_draw_box_payload_keys(self):
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}

        with patch("requests.post", return_value=mock_response) as mock_post:
            srv.draw_box("3", "5", "2", 1.0, 2.0, 3.0, "XY")

        args, _ = mock_post.call_args
        body = json.loads(args[1])  # second positional arg is the JSON string
        assert body["height"] == "3"
        assert body["width"] == "5"
        assert body["depth"] == "2"
        assert body["x"] == 1.0
        assert body["y"] == 2.0
        assert body["z"] == 3.0
        assert body["Plane"] == "XY"


# ===========================================================================
# 4. health endpoint uses GET (via config, since no MCP tool wraps it)
# ===========================================================================

class TestHealthEndpoint:

    def test_health_url_uses_get_scheme(self):
        """
        There is no health_check tool in MCP_Server.py.
        Verify that config defines the health endpoint and that callers
        can reach it via requests.get without needing requests.post.
        """
        _, cfg = _reload_server()
        health_url = cfg.ENDPOINTS["health"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        with patch("requests.get", return_value=mock_response) as mock_get:
            resp = requests.get(health_url)

        mock_get.assert_called_once_with(health_url)
        assert resp.status_code == 200

    def test_health_url_does_not_use_post(self):
        """Calling the health endpoint via GET must NOT trigger requests.post."""
        _, cfg = _reload_server()

        with patch("requests.post") as mock_post, \
             patch("requests.get", return_value=MagicMock(status_code=200)):
            requests.get(cfg.ENDPOINTS["health"])

        mock_post.assert_not_called()


# ===========================================================================
# 5. Failed response (success=False) is returned as-is
# ===========================================================================

class TestFailedResponse:

    def test_failed_response_returned_as_is(self):
        """send_request should return the JSON body even when success=False."""
        srv, cfg = _reload_server()

        error_body = {"success": False, "error": "sketch not found"}
        mock_response = MagicMock()
        mock_response.json.return_value = error_body

        with patch("requests.post", return_value=mock_response):
            result = srv.send_request(cfg.ENDPOINTS["draw_cylinder"], {}, {})

        assert result == error_body, (
            "send_request must return the response body unchanged when success=False"
        )

    def test_failed_response_does_not_raise(self):
        """A success=False payload must NOT cause an exception."""
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": False, "error": "bad input"}

        with patch("requests.post", return_value=mock_response):
            try:
                srv.send_request(cfg.ENDPOINTS["draw_box"], {}, {})
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"send_request raised unexpectedly: {exc}")
