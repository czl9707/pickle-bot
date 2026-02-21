"""Tests for agents API router."""

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
        agents_path = workspace / "agents"
        agents_path.mkdir()

        # Create a test agent
        test_agent_dir = agents_path / "test-agent"
        test_agent_dir.mkdir()
        (test_agent_dir / "AGENT.md").write_text("""---
name: Test Agent
description: A test agent
---
You are a test agent.
""")

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListAgents:
    def test_list_agents_returns_empty_list_when_no_agents(self):
        """GET /agents returns empty list when no agents exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "agents").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/agents")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_agents_returns_agents(self, client):
        """GET /agents returns list of agents."""
        response = client.get("/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["id"] == "test-agent"
        assert agents[0]["name"] == "Test Agent"


class TestGetAgent:
    def test_get_agent_returns_agent(self, client):
        """GET /agents/{id} returns agent definition."""
        response = client.get("/agents/test-agent")

        assert response.status_code == 200
        agent = response.json()
        assert agent["id"] == "test-agent"
        assert agent["name"] == "Test Agent"
        assert agent["description"] == "A test agent"
        assert "You are a test agent" in agent["system_prompt"]

    def test_get_agent_not_found(self, client):
        """GET /agents/{id} returns 404 for non-existent agent."""
        response = client.get("/agents/nonexistent")

        assert response.status_code == 404
