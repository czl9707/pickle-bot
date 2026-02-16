"""Tests for SkillLoader."""

from pathlib import Path
from tempfile import TemporaryDirectory

from picklebot.core.skill_loader import SkillDef, SkillLoader


class TestSkillLoaderDiscovery:
    """Tests for SkillLoader.discover_skills() method."""

    def test_discover_skills_valid_skill(self):
        """Test discover_skills finds and parses valid skill with content."""
        with TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir)

            # Create valid skill directory
            skill_dir = skills_path / "test-skill"
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

            loader = SkillLoader(skills_path)
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

    def test_load_skill_returns_full_content(self, tmp_path):
        """Test load_skill returns SkillDef with full content."""
        skill_dir = tmp_path / "test-skill"
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

        loader = SkillLoader(tmp_path)
        skill_def = loader.load_skill("test-skill")

        assert skill_def.id == "test-skill"
        assert skill_def.name == "Test Skill"
        assert skill_def.description == "A test skill"
        assert "# Test Skill" in skill_def.content
        assert "This is the skill content." in skill_def.content
