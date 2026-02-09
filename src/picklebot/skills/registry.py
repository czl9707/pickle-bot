"""Skill registry for managing available skills."""

import asyncio
from pathlib import Path
from typing import Any

from picklebot.skills.base import BaseSkill


class SkillRegistry:
    """
    Registry for all available skills.

    Handles skill registration, retrieval, and tool schema generation
    for LiteLLM function calling.
    """

    def __init__(self):
        """Initialize an empty skill registry."""
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """
        Register a skill.

        Args:
            skill: The skill to register
        """
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        """
        Get a skill by name.

        Args:
            name: Name of the skill

        Returns:
            The skill if found, None otherwise
        """
        return self._skills.get(name)

    def list_all(self) -> list[BaseSkill]:
        """List all registered skills."""
        return list(self._skills.values())

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Get tool schemas for all registered skills.

        Returns:
            List of tool schemas for LiteLLM function calling
        """
        return [skill.get_tool_schema() for skill in self._skills.values()]

    async def execute_tool(self, name: str, **kwargs: Any) -> str:
        """
        Execute a skill by name.

        Args:
            name: Name of the skill to execute
            **kwargs: Arguments to pass to the skill

        Returns:
            String result of the skill execution

        Raises:
            ValueError: If skill is not found
        """
        skill = self.get(name)
        if skill is None:
            raise ValueError(f"Skill not found: {name}")

        return await skill.execute(**kwargs)

    def load_from_directory(self, directory: Path) -> None:
        """
        Load skills from a directory.

        Skills should be Python files with a `register_skills(registry)` function.

        Args:
            directory: Path to the skills directory
        """
        if not directory.exists():
            return

        for skill_file in directory.glob("*.py"):
            if skill_file.name.startswith("_"):
                continue

            # Dynamic import could be added here for loading user skills
            # For now, we rely on built-in skills being imported directly
            pass


# Global singleton registry
_global_registry: SkillRegistry | None = None


def get_global_registry() -> SkillRegistry:
    """Get the global skill registry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
