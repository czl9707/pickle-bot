"""Tests for SkillLoader."""

from pathlib import Path

import pytest

from picklebot.core.skill_loader import SkillDef, SkillLoader
from picklebot.utils.config import Config, LLMConfig
from picklebot.utils.def_loader import DefNotFoundError


class TestSkillLoaderDiscovery:
    """Tests for SkillLoader.discover_skills() method."""

    @pytest.fixture
    def test_config(self, tmp_path):
        return Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
            default_agent="test",
        )

    def test_discover_skills_valid_skill(self, test_config):
        """Test discover_skills finds and parses valid skill with content."""
        # Create skills directory
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

# Test Skill Content

This is the skill content.
"""
        )

        loader = SkillLoader(test_config)
        result = loader.discover_skills()

        assert len(result) == 1
        assert result[0].id == "test-skill"
        assert result[0].name == "Test Skill"
        assert result[0].description == "A test skill"
        # Content should now be included in discover_skills result
        assert result[0].content == "# Test Skill Content\n\nThis is the skill content."
        # Verify it's a SkillDef instance
        assert isinstance(result[0], SkillDef)


class TestSkillLoaderLoad:
    """Tests for SkillLoader.load_skill() method."""

    @pytest.fixture
    def test_config(self, tmp_path):
        return Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
            default_agent="test",
        )

    def test_load_skill_returns_full_content(self, test_config):
        """Test load_skill returns SkillDef with full content."""
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_content = """---
name: Test Skill
description: A test skill
---

# Test Skill

This is the skill content.
More content here.
"""
        skill_file.write_text(skill_content)

        loader = SkillLoader(test_config)
        skill_def = loader.load_skill("test-skill")

        assert skill_def.id == "test-skill"
        assert skill_def.name == "Test Skill"
        assert skill_def.description == "A test skill"
        assert "# Test Skill" in skill_def.content
        assert "This is the skill content." in skill_def.content

    def test_load_skill_raises_not_found(self, test_config):
        """Test load_skill raises DefNotFoundError for missing skill."""
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        loader = SkillLoader(test_config)

        with pytest.raises(DefNotFoundError) as exc:
            loader.load_skill("nonexistent")

        assert exc.value.def_id == "nonexistent"


class TestSkillLoaderTemplateSubstitution:
    """Tests for template variable substitution in skill content."""

    @pytest.fixture
    def test_config(self, tmp_path):
        return Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
            default_agent="test",
        )

    def test_substitutes_template_variables(self, test_config):
        """Skill content can use template variables."""
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

Workspace is at: {{workspace}}
"""
        )

        loader = SkillLoader(test_config)
        skill_def = loader.load_skill("test-skill")

        expected = f"Workspace is at: {test_config.workspace}"
        assert expected in skill_def.content

    def test_substitutes_multiple_variables(self, test_config):
        """Skill content can use multiple template variables."""
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

Skills: {{skills_path}}
Memories: {{memories_path}}
Crons: {{crons_path}}
"""
        )

        loader = SkillLoader(test_config)
        skill_def = loader.load_skill("test-skill")

        assert str(test_config.skills_path) in skill_def.content
        assert str(test_config.memories_path) in skill_def.content
        assert str(test_config.crons_path) in skill_def.content

    def test_no_template_variables_unchanged(self, test_config):
        """Skill without templates loads normally."""
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

No templates here.
"""
        )

        loader = SkillLoader(test_config)
        skill_def = loader.load_skill("test-skill")

        assert skill_def.content == "No templates here."
