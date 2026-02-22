"""Tests for config API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import yaml

from picklebot.api import create_app
from picklebot.api.schemas import ConfigUpdate
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
            chat_max_history=50,
            job_max_history=500,
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client, workspace


class TestGetConfig:
    def test_get_config_returns_config(self, client):
        """GET /config returns current config with safe fields."""
        client, workspace = client

        response = client.get("/config")

        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "pickle"
        assert config["chat_max_history"] == 50
        assert config["job_max_history"] == 500

    def test_get_config_excludes_sensitive_fields(self, client):
        """GET /config does not expose sensitive fields like api_key."""
        client, workspace = client

        response = client.get("/config")

        assert response.status_code == 200
        config = response.json()
        # api_key should not be in response
        assert "api_key" not in config
        assert "llm" not in config  # entire llm config is hidden


class TestUpdateConfig:
    def test_update_config_partial_update(self, client):
        """PATCH /config performs partial update."""
        client, workspace = client

        # Update only default_agent
        update_data = ConfigUpdate(default_agent="new-agent")

        response = client.patch(
            "/config", json=update_data.model_dump(exclude_none=True)
        )

        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "new-agent"
        assert config["chat_max_history"] == 50  # unchanged
        assert config["job_max_history"] == 500  # unchanged

    def test_update_config_writes_to_user_config(self, client):
        """PATCH /config writes changes to config.user.yaml."""
        client, workspace = client

        # Update config
        update_data = ConfigUpdate(
            default_agent="updated-agent",
            chat_max_history=100,
        )

        response = client.patch(
            "/config", json=update_data.model_dump(exclude_none=True)
        )

        assert response.status_code == 200

        # Verify config.user.yaml was created
        user_config_path = workspace / "config.user.yaml"
        assert user_config_path.exists()

        # Verify content
        with open(user_config_path) as f:
            user_config = yaml.safe_load(f)

        assert user_config["default_agent"] == "updated-agent"
        assert user_config["chat_max_history"] == 100
        assert "job_max_history" not in user_config  # not updated

    def test_update_config_preserves_existing_user_config(self, client):
        """PATCH /config preserves existing config.user.yaml fields."""
        client, workspace = client

        # Create existing user config
        user_config_path = workspace / "config.user.yaml"
        existing_config = {
            "default_agent": "existing-agent",
            "other_field": "should_be_preserved",
        }
        with open(user_config_path, "w") as f:
            yaml.dump(existing_config, f)

        # Update only chat_max_history
        update_data = ConfigUpdate(chat_max_history=75)
        response = client.patch(
            "/config", json=update_data.model_dump(exclude_none=True)
        )

        assert response.status_code == 200

        # Verify existing field is preserved
        with open(user_config_path) as f:
            user_config = yaml.safe_load(f)

        assert user_config["default_agent"] == "existing-agent"
        assert user_config["chat_max_history"] == 75
        assert user_config["other_field"] == "should_be_preserved"

    def test_update_config_multiple_fields(self, client):
        """PATCH /config can update multiple fields at once."""
        client, workspace = client

        update_data = ConfigUpdate(
            default_agent="multi-agent",
            chat_max_history=200,
            job_max_history=1000,
        )

        response = client.patch(
            "/config", json=update_data.model_dump(exclude_none=True)
        )

        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "multi-agent"
        assert config["chat_max_history"] == 200
        assert config["job_max_history"] == 1000
