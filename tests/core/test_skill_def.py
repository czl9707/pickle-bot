"""Tests for skill definition models."""
import pytest
from picklebot.core.skill_def import SkillMetadata, SkillDef


def test_skill_metadata_creation():
    """Test SkillMetadata can be created with required fields."""
    metadata = SkillMetadata(
        id="brainstorming",
        name="Brainstorming Ideas",
        description="Turn ideas into designs"
    )
    assert metadata.id == "brainstorming"
    assert metadata.name == "Brainstorming Ideas"
    assert metadata.description == "Turn ideas into designs"


def test_skill_def_creation():
    """Test SkillDef can be created with content."""
    skill_def = SkillDef(
        id="debugging",
        name="Systematic Debugging",
        description="Fix bugs systematically",
        content="# Debugging\n\nSteps to debug..."
    )
    assert skill_def.id == "debugging"
    assert skill_def.content == "# Debugging\n\nSteps to debug..."


def test_skill_metadata_forbids_extra_fields():
    """Test SkillMetadata rejects extra fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SkillMetadata(
            id="test",
            name="Test",
            description="Test skill",
            extra_field="not allowed"
        )
