"""Tests for crons API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from picklebot.api import create_app
from picklebot.api.schemas import CronCreate
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        crons_path = workspace / "crons"
        crons_path.mkdir()

        # Create a test cron
        test_cron_dir = crons_path / "test-cron"
        test_cron_dir.mkdir()
        (test_cron_dir / "CRON.md").write_text(
            """---
name: Test Cron
agent: pickle
schedule: "0 * * * *"
---
Check for updates.
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


class TestListCrons:
    def test_list_crons_returns_empty_list_when_no_crons(self):
        """GET /crons returns empty list when no crons exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "crons").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/crons")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_crons_returns_crons(self, client):
        """GET /crons returns list of crons."""
        response = client.get("/crons")

        assert response.status_code == 200
        crons = response.json()
        assert len(crons) == 1
        assert crons[0]["id"] == "test-cron"
        assert crons[0]["name"] == "Test Cron"


class TestGetCron:
    def test_get_cron_returns_cron(self, client):
        """GET /crons/{id} returns cron definition."""
        response = client.get("/crons/test-cron")

        assert response.status_code == 200
        cron = response.json()
        assert cron["id"] == "test-cron"
        assert cron["name"] == "Test Cron"
        assert cron["agent"] == "pickle"
        assert cron["schedule"] == "0 * * * *"
        assert "Check for updates" in cron["prompt"]

    def test_get_cron_not_found(self, client):
        """GET /crons/{id} returns 404 for non-existent cron."""
        response = client.get("/crons/nonexistent")

        assert response.status_code == 404


class TestCreateCron:
    def test_create_cron(self, client):
        """POST /crons/{id} creates a new cron."""
        cron_data = CronCreate(
            name="New Cron",
            agent="pickle",
            schedule="*/30 * * * *",
            prompt="Run this every 30 minutes.",
            one_off=False,
        )

        response = client.post(
            "/crons/new-cron",
            json=cron_data.model_dump(),
        )

        assert response.status_code == 201
        cron = response.json()
        assert cron["id"] == "new-cron"
        assert cron["name"] == "New Cron"
        assert cron["agent"] == "pickle"
        assert cron["schedule"] == "*/30 * * * *"

        # Verify it was created
        get_response = client.get("/crons/new-cron")
        assert get_response.status_code == 200

    def test_create_cron_already_exists(self, client):
        """POST /crons/{id} returns 409 if cron already exists."""
        cron_data = CronCreate(
            name="Duplicate Cron",
            agent="pickle",
            schedule="0 * * * *",
            prompt="This should fail.",
            one_off=False,
        )

        response = client.post(
            "/crons/test-cron",
            json=cron_data.model_dump(),
        )

        assert response.status_code == 409


class TestUpdateCron:
    def test_update_cron(self, client):
        """PUT /crons/{id} updates an existing cron."""
        cron_data = CronCreate(
            name="Updated Cron",
            agent="cookie",
            schedule="*/15 * * * *",
            prompt="Updated prompt.",
            one_off=True,
        )

        response = client.put(
            "/crons/test-cron",
            json=cron_data.model_dump(),
        )

        assert response.status_code == 200
        cron = response.json()
        assert cron["name"] == "Updated Cron"
        assert cron["agent"] == "cookie"
        assert cron["schedule"] == "*/15 * * * *"
        assert cron["one_off"] is True

    def test_update_cron_not_found(self, client):
        """PUT /crons/{id} returns 404 for non-existent cron."""
        cron_data = CronCreate(
            name="Nonexistent Cron",
            agent="pickle",
            schedule="0 * * * *",
            prompt="This should fail.",
            one_off=False,
        )

        response = client.put(
            "/crons/nonexistent",
            json=cron_data.model_dump(),
        )

        assert response.status_code == 404


class TestDeleteCron:
    def test_delete_cron(self, client):
        """DELETE /crons/{id} deletes a cron."""
        response = client.delete("/crons/test-cron")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/crons/test-cron")
        assert get_response.status_code == 404

    def test_delete_cron_not_found(self, client):
        """DELETE /crons/{id} returns 404 for non-existent cron."""
        response = client.delete("/crons/nonexistent")

        assert response.status_code == 404
