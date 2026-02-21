"""Tests for skills API router."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from picklebot.api import create_app
from picklebot.api.schemas import SkillCreate
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        skills_path = workspace / "skills"
        skills_path.mkdir()

        # Create a test skill
        test_skill_dir = skills_path / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text("""---
name: Test Skill
description: A test skill
---
# Test Skill

This is a test skill.
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


class TestListSkills:
    def test_list_skills_returns_empty_list_when_no_skills(self):
        """GET /skills returns empty list when no skills exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "skills").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/skills")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_skills_returns_skills(self, client):
        """GET /skills returns list of skills."""
        response = client.get("/skills")

        assert response.status_code == 200
        skills = response.json()
        assert len(skills) == 1
        assert skills[0]["id"] == "test-skill"
        assert skills[0]["name"] == "Test Skill"


class TestGetSkill:
    def test_get_skill_returns_skill(self, client):
        """GET /skills/{id} returns skill definition."""
        response = client.get("/skills/test-skill")

        assert response.status_code == 200
        skill = response.json()
        assert skill["id"] == "test-skill"
        assert skill["name"] == "Test Skill"
        assert skill["description"] == "A test skill"
        assert "This is a test skill" in skill["content"]

    def test_get_skill_not_found(self, client):
        """GET /skills/{id} returns 404 for non-existent skill."""
        response = client.get("/skills/nonexistent")

        assert response.status_code == 404


class TestCreateSkill:
    def test_create_skill(self, client):
        """POST /skills/{id} creates a new skill."""
        skill_data = SkillCreate(
            name="New Skill",
            description="A new skill",
            content="# New Skill\n\nThis is a new skill.",
        )

        response = client.post(
            "/skills/new-skill",
            json=skill_data.model_dump(),
        )

        assert response.status_code == 201
        skill = response.json()
        assert skill["id"] == "new-skill"
        assert skill["name"] == "New Skill"

        # Verify it was created
        get_response = client.get("/skills/new-skill")
        assert get_response.status_code == 200


class TestUpdateSkill:
    def test_update_skill(self, client):
        """PUT /skills/{id} updates an existing skill."""
        skill_data = SkillCreate(
            name="Updated Skill",
            description="Updated description",
            content="# Updated Skill\n\nThis is updated.",
        )

        response = client.put(
            "/skills/test-skill",
            json=skill_data.model_dump(),
        )

        assert response.status_code == 200
        skill = response.json()
        assert skill["name"] == "Updated Skill"


class TestDeleteSkill:
    def test_delete_skill(self, client):
        """DELETE /skills/{id} deletes a skill."""
        response = client.delete("/skills/test-skill")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/skills/test-skill")
        assert get_response.status_code == 404
