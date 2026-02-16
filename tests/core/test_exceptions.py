"""Tests for custom exceptions."""

import pytest
from picklebot.core.exceptions import SkillNotFoundError


def test_skill_not_found_error_can_be_raised():
    """Test SkillNotFoundError can be raised with message."""
    with pytest.raises(SkillNotFoundError) as exc_info:
        raise SkillNotFoundError("Skill 'test' not found")

    assert str(exc_info.value) == "Skill 'test' not found"


def test_skill_not_found_error_is_exception():
    """Test SkillNotFoundError is an Exception."""
    assert issubclass(SkillNotFoundError, Exception)
