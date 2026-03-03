"""Tests for agents API router."""

import pytest

from picklebot.api.schemas import AgentCreate


@pytest.fixture
def client(api_client_with_agent):
    """Create test client with test agent."""
    client, _ = api_client_with_agent
    return client


class TestListAgents:
    def test_list_agents_returns_empty_list_when_no_agents(self, api_client):
        """GET /agents returns empty list when no agents exist."""
        client, _ = api_client
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
        assert "You are a test assistant" in agent["agent_md"]

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
            agent_md="You are a new agent.",
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
            agent_md="You are updated.",
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
