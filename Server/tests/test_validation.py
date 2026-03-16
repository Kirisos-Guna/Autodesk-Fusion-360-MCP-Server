"""
Tests for input validation and configuration correctness.

Covers:
1. send_request raises on HTTP 4xx (raise_for_status behaviour)
2. send_request raises after max retries are exhausted
3. config.HEADERS contains Content-Type: application/json
4. config.API_KEY is read from the FUSION_API_KEY env var
5. config.BASE_URL is composed from FUSION_HOST and FUSION_PORT env vars
"""
import sys
import os
import importlib

import pytest
from unittest.mock import patch, MagicMock
import requests

# ---------------------------------------------------------------------------
# Ensure the Server package is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helper: reload config (and optionally MCP_Server) after env vars are set
# ---------------------------------------------------------------------------

def _reload_config():
    """Reload config so that os.environ changes are picked up."""
    import config as cfg
    importlib.reload(cfg)
    return cfg


def _reload_server():
    """Reload both config and MCP_Server with FastMCP stubbed out."""
    fake_mcp_pkg = MagicMock()
    fake_fastmcp_mod = MagicMock()
    fake_fastmcp_mod.FastMCP = MagicMock(return_value=MagicMock())

    with patch.dict(
        sys.modules,
        {
            "mcp": fake_mcp_pkg,
            "mcp.server": MagicMock(),
            "mcp.server.fastmcp": fake_fastmcp_mod,
        },
    ):
        import config as cfg
        importlib.reload(cfg)

        import MCP_Server as srv
        importlib.reload(srv)

    return srv, cfg


# ===========================================================================
# 1. send_request raises on HTTP 4xx (raise_for_status)
# ===========================================================================

class TestRaiseForStatus:
    """
    The current send_request implementation does NOT call raise_for_status.
    It tries to call response.json() directly.  These tests document the
    EXPECTED behaviour: a 4xx response that raises HTTPError on
    raise_for_status() should propagate out of send_request.

    To make this suite green the implementation must call
    response.raise_for_status() before response.json().
    """

    def test_raises_on_404(self):
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "404 Not Found"
        )

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                srv.send_request(cfg.ENDPOINTS["draw_box"], {"key": "val"}, {})

    def test_raises_on_400(self):
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "400 Bad Request"
        )

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                srv.send_request(cfg.ENDPOINTS["draw_cylinder"], {}, {})

    def test_raises_on_500(self):
        """5xx errors are also HTTPError subclasses and must propagate."""
        srv, cfg = _reload_server()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "500 Internal Server Error"
        )

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                srv.send_request(cfg.ENDPOINTS["draw_box"], {}, {})


# ===========================================================================
# 2. send_request raises after max retries exhausted
# ===========================================================================

class TestMaxRetriesExhausted:

    def test_raises_request_exception_after_three_failures(self):
        srv, cfg = _reload_server()

        with patch(
            "requests.post",
            side_effect=requests.RequestException("connection refused"),
        ) as mock_post:
            with pytest.raises(requests.RequestException):
                srv.send_request(cfg.ENDPOINTS["test_connection"], {}, {})

        assert mock_post.call_count == 3

    def test_raises_connection_error_subclass(self):
        srv, cfg = _reload_server()

        with patch(
            "requests.post",
            side_effect=requests.ConnectionError("unreachable"),
        ):
            with pytest.raises(requests.RequestException):
                srv.send_request(cfg.ENDPOINTS["test_connection"], {}, {})

    def test_raises_timeout_subclass(self):
        srv, cfg = _reload_server()

        with patch(
            "requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(requests.RequestException):
                srv.send_request(cfg.ENDPOINTS["draw_box"], {}, {})


# ===========================================================================
# 3. config.HEADERS contains Content-Type: application/json
# ===========================================================================

class TestConfigHeaders:

    def test_content_type_header_present(self, monkeypatch):
        monkeypatch.setenv("FUSION_API_KEY", "test-key-123")
        cfg = _reload_config()
        assert cfg.HEADERS.get("Content-Type") == "application/json"

    def test_content_type_header_present_without_api_key(self, monkeypatch):
        monkeypatch.delenv("FUSION_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.HEADERS.get("Content-Type") == "application/json"

    def test_api_key_header_present_when_env_set(self, monkeypatch):
        monkeypatch.setenv("FUSION_API_KEY", "secret-key")
        cfg = _reload_config()
        assert cfg.HEADERS.get("X-API-Key") == "secret-key"

    def test_api_key_header_absent_when_env_empty(self, monkeypatch):
        monkeypatch.setenv("FUSION_API_KEY", "")
        cfg = _reload_config()
        assert "X-API-Key" not in cfg.HEADERS


# ===========================================================================
# 4. config.API_KEY is read from FUSION_API_KEY env var
# ===========================================================================

class TestConfigApiKey:

    def test_api_key_set_from_env(self, monkeypatch):
        monkeypatch.setenv("FUSION_API_KEY", "my-secret")
        cfg = _reload_config()
        assert cfg.API_KEY == "my-secret"

    def test_api_key_defaults_to_empty_string(self, monkeypatch):
        monkeypatch.delenv("FUSION_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.API_KEY == ""

    def test_api_key_changes_with_env(self, monkeypatch):
        monkeypatch.setenv("FUSION_API_KEY", "first-key")
        cfg = _reload_config()
        assert cfg.API_KEY == "first-key"

        monkeypatch.setenv("FUSION_API_KEY", "second-key")
        cfg = _reload_config()
        assert cfg.API_KEY == "second-key"


# ===========================================================================
# 5. config.BASE_URL uses FUSION_HOST and FUSION_PORT env vars
# ===========================================================================

class TestConfigBaseUrl:

    def test_base_url_uses_host_and_port(self, monkeypatch):
        monkeypatch.setenv("FUSION_HOST", "192.168.1.100")
        monkeypatch.setenv("FUSION_PORT", "8080")
        monkeypatch.delenv("FUSION_BASE_URL", raising=False)
        cfg = _reload_config()
        assert "192.168.1.100" in cfg.BASE_URL
        assert "8080" in cfg.BASE_URL

    def test_base_url_default_host(self, monkeypatch):
        monkeypatch.delenv("FUSION_HOST", raising=False)
        monkeypatch.delenv("FUSION_PORT", raising=False)
        monkeypatch.delenv("FUSION_BASE_URL", raising=False)
        cfg = _reload_config()
        assert "127.0.0.1" in cfg.BASE_URL

    def test_base_url_default_port(self, monkeypatch):
        monkeypatch.delenv("FUSION_HOST", raising=False)
        monkeypatch.delenv("FUSION_PORT", raising=False)
        monkeypatch.delenv("FUSION_BASE_URL", raising=False)
        cfg = _reload_config()
        assert "5000" in cfg.BASE_URL

    def test_base_url_overridden_by_fusion_base_url(self, monkeypatch):
        monkeypatch.setenv("FUSION_BASE_URL", "http://custom-host:9999")
        cfg = _reload_config()
        assert cfg.BASE_URL == "http://custom-host:9999"

    def test_endpoints_reflect_base_url(self, monkeypatch):
        monkeypatch.setenv("FUSION_HOST", "10.0.0.1")
        monkeypatch.setenv("FUSION_PORT", "7777")
        monkeypatch.delenv("FUSION_BASE_URL", raising=False)
        cfg = _reload_config()
        assert cfg.ENDPOINTS["draw_box"].startswith(cfg.BASE_URL)
        assert "10.0.0.1" in cfg.ENDPOINTS["draw_box"]
        assert "7777" in cfg.ENDPOINTS["draw_box"]
