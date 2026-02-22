"""Tests for sessions API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryMessage
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        history_path = workspace / ".history"
        history_path.mkdir()

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)

        # Create a test session
        context.history_store.create_session("pickle", "test-session")
        context.history_store.save_message(
            "test-session",
            HistoryMessage(role="user", content="Hello"),
        )

        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListSessions:
    def test_list_sessions_returns_empty_list_when_no_sessions(self):
        """GET /sessions returns empty list when no sessions exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".history").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/sessions")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_sessions_returns_sessions(self, client):
        """GET /sessions returns list of sessions."""
        response = client.get("/sessions")

        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["id"] == "test-session"
        assert sessions[0]["agent_id"] == "pickle"
        assert sessions[0]["message_count"] == 1

    def test_list_sessions_excludes_messages(self, client):
        """GET /sessions returns session metadata without messages."""
        response = client.get("/sessions")

        sessions = response.json()
        # Messages should not be included in list view
        assert "messages" not in sessions[0]


class TestGetSession:
    def test_get_session_returns_session_with_messages(self, client):
        """GET /sessions/{id} returns session with messages."""
        response = client.get("/sessions/test-session")

        assert response.status_code == 200
        session = response.json()
        assert session["id"] == "test-session"
        assert session["agent_id"] == "pickle"
        assert session["message_count"] == 1
        assert "messages" in session
        assert len(session["messages"]) == 1
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][0]["content"] == "Hello"

    def test_get_session_not_found(self, client):
        """GET /sessions/{id} returns 404 for non-existent session."""
        response = client.get("/sessions/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_with_multiple_messages(self, client):
        """GET /sessions/{id} returns all messages in order."""
        # Create a new session with multiple messages
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            history_path = workspace / ".history"
            history_path.mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)

            context.history_store.create_session("pickle", "multi-session")
            context.history_store.save_message(
                "multi-session",
                HistoryMessage(role="user", content="First"),
            )
            context.history_store.save_message(
                "multi-session",
                HistoryMessage(role="assistant", content="Second"),
            )
            context.history_store.save_message(
                "multi-session",
                HistoryMessage(role="user", content="Third"),
            )

            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/sessions/multi-session")

        assert response.status_code == 200
        session = response.json()
        assert session["message_count"] == 3
        assert len(session["messages"]) == 3
        assert session["messages"][0]["content"] == "First"
        assert session["messages"][1]["content"] == "Second"
        assert session["messages"][2]["content"] == "Third"


class TestDeleteSession:
    def test_delete_session(self, client):
        """DELETE /sessions/{id} deletes a session."""
        response = client.delete("/sessions/test-session")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/sessions/test-session")
        assert get_response.status_code == 404

    def test_delete_session_not_found(self, client):
        """DELETE /sessions/{id} returns 404 for non-existent session."""
        response = client.delete("/sessions/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_session_removes_from_list(self, client):
        """DELETE /sessions/{id} removes session from list."""
        # Delete the session
        response = client.delete("/sessions/test-session")
        assert response.status_code == 204

        # Verify it's not in the list
        list_response = client.get("/sessions")
        assert list_response.status_code == 200
        sessions = list_response.json()
        assert len(sessions) == 0
