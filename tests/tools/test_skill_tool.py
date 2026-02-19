"""Tests for skill tool factory."""

import pytest

from picklebot.core.skill_loader import SkillLoader
from picklebot.tools.skill_tool import create_skill_tool
from picklebot.utils.config import Config, LLMConfig


class TestCreateSkillTool:
    """Tests for create_skill_tool factory function."""

    @pytest.fixture
    def test_config(self, tmp_path):
        return Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
            default_agent="test",
        )

    def test_create_skill_tool_returns_none_when_no_skills(self, test_config):
        """create_skill_tool should return None when no skills available."""
        loader = SkillLoader(test_config)
        tool_func = create_skill_tool(loader)
        assert tool_func is None

    def test_create_skill_tool_returns_callable(self, test_config):
        """create_skill_tool should return a callable tool function."""
        # Setup - create a valid skill
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: Test Skill
description: A test skill
---

# Test Skill
"""
        )

        loader = SkillLoader(test_config)
        tool_func = create_skill_tool(loader)

        # Should be a FunctionTool with execute method
        assert tool_func is not None
        assert hasattr(tool_func, "execute")
        assert callable(tool_func.execute)

    def test_skill_tool_has_correct_schema(self, test_config):
        """Skill tool should have correct name, description, and parameters."""
        # Setup - create skills
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        for skill_id, name, desc in [
            ("code-review", "Code Review", "Review code for best practices"),
            ("commit", "Commit", "Create git commits"),
        ]:
            skill_dir = skills_dir / skill_id
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                f"""---
name: {name}
description: {desc}
---

# {name}
"""
            )

        loader = SkillLoader(test_config)
        tool_func = create_skill_tool(loader)

        assert tool_func is not None
        # Check tool properties
        assert tool_func.name == "skill"
        assert "Load and invoke a specialized skill" in tool_func.description
        assert "<skills>" in tool_func.description
        assert 'name="Code Review"' in tool_func.description
        assert "Review code for best practices" in tool_func.description
        assert 'name="Commit"' in tool_func.description

        # Check parameters schema
        params = tool_func.parameters
        assert params["type"] == "object"
        assert "skill_name" in params["properties"]
        assert params["properties"]["skill_name"]["type"] == "string"
        assert set(params["properties"]["skill_name"]["enum"]) == {
            "code-review",
            "commit",
        }
        assert params["required"] == ["skill_name"]

    @pytest.mark.anyio
    async def test_skill_tool_loads_content(self, test_config):
        """Skill tool should load and return skill content."""
        # Setup - create a valid skill
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: Test Skill
description: A test skill
---

# Test Skill

This is the skill content.
"""
        )

        loader = SkillLoader(test_config)
        tool_func = create_skill_tool(loader)

        assert tool_func is not None
        # Execute
        result = await tool_func.execute(skill_name="test-skill")

        # Verify
        assert "# Test Skill" in result
        assert "This is the skill content." in result

    @pytest.mark.anyio
    async def test_skill_tool_handles_missing_skill(self, test_config):
        """Skill tool should return error message for missing skill."""
        # Setup - create one skill
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "existing-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: Existing Skill
description: An existing skill
---

# Existing Skill
"""
        )

        loader = SkillLoader(test_config)
        tool_func = create_skill_tool(loader)

        assert tool_func is not None
        # Execute - try to load a skill that doesn't exist
        result = await tool_func.execute(skill_name="nonexistent-skill")

        # Verify - should return error message
        assert "Error:" in result
        assert "nonexistent-skill" in result
        assert "not found" in result
