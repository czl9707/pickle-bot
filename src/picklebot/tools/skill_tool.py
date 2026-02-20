"""Skill tool factory for creating dynamic skill tool."""

from typing import TYPE_CHECKING

from picklebot.tools.base import tool
from picklebot.core.skill_loader import SkillLoader

if TYPE_CHECKING:
    from picklebot.frontend import Frontend


def create_skill_tool(skill_loader: SkillLoader):
    """Factory function to create skill tool with dynamic schema.

    Args:
        skill_loader: SkillLoader instance for discovering and loading skills

    Returns:
        Async tool function for loading skills, or None if no skills available
    """
    skill_metadata = skill_loader.discover_skills()

    if not skill_metadata:
        return None

    # Build XML description of available skills
    skills_xml = "<skills>\n"
    for meta in skill_metadata:
        skills_xml += f'  <skill name="{meta.name}">{meta.description}</skill>\n'
    skills_xml += "</skills>"

    # Build enum of skill IDs
    skill_enum = [meta.id for meta in skill_metadata]

    @tool(
        name="skill",
        description=f"Load and invoke a specialized skill. {skills_xml}",
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": skill_enum,
                    "description": "The name of the skill to load",
                }
            },
            "required": ["skill_name"],
        },
    )
    async def skill_tool(frontend: "Frontend", skill_name: str) -> str:
        """Load and return skill content.

        Args:
            frontend: Frontend for displaying output
            skill_name: The ID of the skill to load

        Returns:
            Skill content or error message
        """
        try:
            skill_def = skill_loader.load_skill(skill_name)
            return skill_def.content
        except Exception:
            return f"Error: Skill '{skill_name}' not found. It may have been removed or is unavailable."

    return skill_tool
