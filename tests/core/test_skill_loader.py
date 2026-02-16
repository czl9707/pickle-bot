"""Tests for SkillLoader."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from picklebot.core.skill_loader import SkillDef, SkillLoader, SkillNotFoundError


class TestSkillLoaderDiscovery:
    """Tests for SkillLoader.discover_skills() method."""

    def test_discover_skills_empty_directory(self):
        """Test discover_skills returns empty list for empty directory."""
        with TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir)
            loader = SkillLoader(skills_path)
            result = loader.discover_skills()
            assert result == []

    def test_discover_skills_missing_directory(self):
        """Test discover_skills returns empty list for missing directory."""
        skills_path = Path("/nonexistent/skills/path")
        loader = SkillLoader(skills_path)
        result = loader.discover_skills()
        assert result == []

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

    def test_discover_skills_skips_invalid_skill(self, caplog):
        """Test discover_skills skips skills with invalid SKILL.md."""
        with TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir)

            # Create skill directory with invalid SKILL.md (no frontmatter)
            skill_dir = skills_path / "invalid-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("This has no frontmatter")

            loader = SkillLoader(skills_path)
            with caplog.at_level(logging.WARNING):
                result = loader.discover_skills()

            assert result == []
            # Skipped due to missing required fields (no frontmatter = no name/description)
            assert "Missing required fields" in caplog.text

    def test_discover_skills_skips_non_directories(self):
        """Test discover_skills skips non-directory files in skills path."""
        with TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir)

            # Create a regular file (not a directory)
            regular_file = skills_path / "regular-file.md"
            regular_file.write_text("not a directory")

            loader = SkillLoader(skills_path)
            result = loader.discover_skills()

            assert result == []


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

    def test_load_skill_raises_not_found(self, tmp_path):
        """Test load_skill raises SkillNotFoundError for missing skill."""
        loader = SkillLoader(tmp_path)

        with pytest.raises(SkillNotFoundError):
            loader.load_skill("nonexistent-skill")
