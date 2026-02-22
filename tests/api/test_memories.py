"""Tests for memories API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        memories_path = workspace / "memories"
        topics_path = memories_path / "topics"
        topics_path.mkdir(parents=True)

        # Create a test memory
        (topics_path / "preferences.md").write_text(
            "# User Preferences\n\nLikes: Python"
        )

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListMemories:
    def test_list_memories_returns_empty_list_when_no_memories(self):
        """GET /memories returns empty list when no memories exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "memories").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/memories")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_memories_returns_memories(self, client):
        """GET /memories returns list of memory files."""
        response = client.get("/memories")

        assert response.status_code == 200
        memories = response.json()
        assert len(memories) == 1
        assert memories[0] == "topics/preferences.md"

    def test_list_memories_returns_nested_files_recursively(self, client):
        """GET /memories returns nested files recursively."""
        # Create nested structure
        memories_path = client.app.state.context.config.memories_path
        projects_path = memories_path / "projects" / "active"
        projects_path.mkdir(parents=True)
        (projects_path / "pickle-bot.md").write_text("# Pickle Bot Project")

        daily_path = memories_path / "daily-notes"
        daily_path.mkdir(parents=True)
        (daily_path / "2024-01-15.md").write_text("# Daily Notes")

        response = client.get("/memories")

        assert response.status_code == 200
        memories = response.json()
        assert len(memories) == 3
        # Should be sorted
        assert "daily-notes/2024-01-15.md" in memories
        assert "projects/active/pickle-bot.md" in memories
        assert "topics/preferences.md" in memories


class TestGetMemory:
    def test_get_memory_returns_content(self, client):
        """GET /memories/{path} returns memory content."""
        response = client.get("/memories/topics/preferences.md")

        assert response.status_code == 200
        memory = response.json()
        assert memory["path"] == "topics/preferences.md"
        assert "# User Preferences" in memory["content"]
        assert "Likes: Python" in memory["content"]

    def test_get_memory_nested_path(self, client):
        """GET /memories/{path} works with nested paths."""
        memories_path = client.app.state.context.config.memories_path
        projects_path = memories_path / "projects" / "active"
        projects_path.mkdir(parents=True)
        (projects_path / "pickle-bot.md").write_text("# Pickle Bot")

        response = client.get("/memories/projects/active/pickle-bot.md")

        assert response.status_code == 200
        memory = response.json()
        assert memory["path"] == "projects/active/pickle-bot.md"
        assert "# Pickle Bot" in memory["content"]

    def test_get_memory_not_found(self, client):
        """GET /memories/{path} returns 404 for non-existent memory."""
        response = client.get("/memories/topics/nonexistent.md")

        assert response.status_code == 404

    def test_get_memory_directory_returns_404(self, client):
        """GET /memories/{path} returns 404 for directories."""
        response = client.get("/memories/topics")

        assert response.status_code == 404


class TestCreateMemory:
    def test_create_memory(self, client):
        """POST /memories/{path} creates a new memory."""
        memory_data = {"content": "# New Memory\n\nThis is a new memory."}

        response = client.post(
            "/memories/projects/new-project.md",
            json=memory_data,
        )

        assert response.status_code == 201
        memory = response.json()
        assert memory["path"] == "projects/new-project.md"
        assert "# New Memory" in memory["content"]

        # Verify it was created
        get_response = client.get("/memories/projects/new-project.md")
        assert get_response.status_code == 200

    def test_create_memory_creates_parent_directories(self, client):
        """POST /memories/{path} creates parent directories if needed."""
        memory_data = {"content": "# Nested Memory"}

        response = client.post(
            "/memories/daily-notes/2024/01/jan.md",
            json=memory_data,
        )

        assert response.status_code == 201
        assert response.json()["path"] == "daily-notes/2024/01/jan.md"

    def test_create_memory_already_exists(self, client):
        """POST /memories/{path} returns 409 if memory already exists."""
        memory_data = {"content": "# Duplicate"}

        # Create it once
        response1 = client.post(
            "/memories/projects/duplicate.md",
            json=memory_data,
        )
        assert response1.status_code == 201

        # Try to create it again
        response2 = client.post(
            "/memories/projects/duplicate.md",
            json=memory_data,
        )
        assert response2.status_code == 409


class TestUpdateMemory:
    def test_update_memory(self, client):
        """PUT /memories/{path} updates an existing memory."""
        memory_data = {"content": "# Updated Preferences\n\nLikes: Python, FastAPI"}

        response = client.put(
            "/memories/topics/preferences.md",
            json=memory_data,
        )

        assert response.status_code == 200
        memory = response.json()
        assert memory["path"] == "topics/preferences.md"
        assert "Updated Preferences" in memory["content"]
        assert "FastAPI" in memory["content"]

    def test_update_memory_not_found(self, client):
        """PUT /memories/{path} returns 404 for non-existent memory."""
        memory_data = {"content": "# Updated"}

        response = client.put(
            "/memories/topics/nonexistent.md",
            json=memory_data,
        )

        assert response.status_code == 404


class TestDeleteMemory:
    def test_delete_memory(self, client):
        """DELETE /memories/{path} deletes a memory."""
        response = client.delete("/memories/topics/preferences.md")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/memories/topics/preferences.md")
        assert get_response.status_code == 404

    def test_delete_memory_not_found(self, client):
        """DELETE /memories/{path} returns 404 for non-existent memory."""
        response = client.delete("/memories/topics/nonexistent.md")

        assert response.status_code == 404
