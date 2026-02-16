"""Skill loader for discovering and loading skills."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from picklebot.utils.def_loader import DefNotFoundError, discover_definitions

if TYPE_CHECKING:
    from picklebot.utils.config import Config

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
SkillNotFoundError = DefNotFoundError


class SkillDef(BaseModel):
    """Loaded skill definition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    content: str


class SkillLoader:
    """Load and manage skill definitions from filesystem."""

    @staticmethod
    def from_config(config: "Config") -> "SkillLoader":
        """Create SkillLoader from config."""
        return SkillLoader(config.skills_path)

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path

    def discover_skills(self) -> list[SkillDef]:
        """Scan skills directory and return list of valid SkillDef."""
        return discover_definitions(
            self.skills_path, "SKILL.md", self._parse_skill_def, logger
        )

    def _parse_skill_def(
        self, def_id: str, frontmatter: dict[str, Any], body: str
    ) -> SkillDef | None:
        """Parse skill definition from frontmatter (callback for discover_definitions)."""
        if "name" not in frontmatter or "description" not in frontmatter:
            logger.warning(f"Missing required fields in skill '{def_id}'")
            return None

        return SkillDef(
            id=def_id,
            name=frontmatter["name"],
            description=frontmatter["description"],
            content=body.strip(),
        )

    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill definition by ID.

        Args:
            skill_id: The skill directory name

        Returns:
            SkillDef with full content

        Raises:
            SkillNotFoundError: If skill doesn't exist
        """
        # Use discover_skills which now returns full SkillDef objects
        skills = self.discover_skills()
        for skill in skills:
            if skill.id == skill_id:
                return skill

        raise DefNotFoundError("skill", skill_id)
