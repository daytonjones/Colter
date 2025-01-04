# tests/test_github_helper.py

from rich.console import Console
from unittest.mock import patch, Mock
import logging
import os
import pytest
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _github_helper import GitHubTracker, GitHubAPIError


@pytest.fixture
def mock_config():
    return {
        "github": {
            "token": "fake_token"
        },
        "smtp": {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "username": "user@example.com",
            "password": "securepassword",
            "sender": "sender@example.com",
            "recipient": "recipient@example.com"
        }
    }

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_logger")

@pytest.fixture
def mock_console():
    return Console()

def test_fetch_repos_success(mock_config, mock_logger, mock_console):
    tracker = GitHubTracker(mock_config, mock_logger, mock_console)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"name": "repo1", "owner": {"login": "user"}, "private": False},
        {"name": "repo2", "owner": {"login": "user"}, "private": True}
    ]

    with patch('requests.get', return_value=mock_response) as mock_get:
        repos = tracker.fetch_repos()
        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"
        assert repos[1]["private"] == True
        mock_get.assert_called_once_with("https://api.github.com/user/repos", headers=tracker.headers)

def test_fetch_repos_failure(mock_config, mock_logger, mock_console):
    tracker = GitHubTracker(mock_config, mock_logger, mock_console)
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    with patch('requests.get', return_value=mock_response) as mock_get:
        with pytest.raises(GitHubAPIError) as exc_info:
            tracker.fetch_repos()
        assert "Failed to fetch repos" in str(exc_info.value)
        mock_get.assert_called_once_with("https://api.github.com/user/repos", headers=tracker.headers)

