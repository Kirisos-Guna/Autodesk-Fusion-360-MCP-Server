import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("FUSION_API_KEY", "test-key-123")
    monkeypatch.setenv("FUSION_HOST", "127.0.0.1")
    monkeypatch.setenv("FUSION_PORT", "5000")

@pytest.fixture
def mock_requests():
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"success": True, "data": {}})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"success": True, "data": {}})
        yield mock_post, mock_get
