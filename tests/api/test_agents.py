"""Tests for agents API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from picklebot.api import create_app
from picklebot.api.schemas import AgentCreate
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
        (test_agent_dir / "AGENT.md").write_text(
            """---
name: Test Agent
description: A test agent
---
You are a test agent.
"""
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


class TestCreateAgent:
    def test_create_agent(self, client):
        """POST /agents/{id} creates a new agent."""
        agent_data = AgentCreate(
            name="New Agent",
            description="A new agent",
            system_prompt="You are a new agent.",
        )

        response = client.post(
            "/agents/new-agent",
            json=agent_data.model_dump(),
        )

        assert response.status_code == 201
        agent = response.json()
        assert agent["id"] == "new-agent"
        assert agent["name"] == "New Agent"

        # Verify it was created
        get_response = client.get("/agents/new-agent")
        assert get_response.status_code == 200


class TestUpdateAgent:
    def test_update_agent(self, client):
        """PUT /agents/{id} updates an existing agent."""
        agent_data = AgentCreate(
            name="Updated Agent",
            description="Updated description",
            system_prompt="You are updated.",
        )

        response = client.put(
            "/agents/test-agent",
            json=agent_data.model_dump(),
        )

        assert response.status_code == 200
        agent = response.json()
        assert agent["name"] == "Updated Agent"


class TestDeleteAgent:
    def test_delete_agent(self, client):
        """DELETE /agents/{id} deletes an agent."""
        response = client.delete("/agents/test-agent")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/agents/test-agent")
        assert get_response.status_code == 404
