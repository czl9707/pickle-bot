"""Skill loader for discovering and loading skills."""

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, ValidationError

from picklebot.utils.def_loader import (
    DefNotFoundError,
    discover_definitions,
    get_template_variables,
    substitute_template,
)

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
        return SkillLoader(config)

    def __init__(self, config: "Config"):
        self.config = config

    def discover_skills(self) -> list[SkillDef]:
        """Scan skills directory and return list of valid SkillDef."""
        return discover_definitions(
            self.config.skills_path, "SKILL.md", self._parse_skill_def
        )

    def _parse_skill_def(
        self, def_id: str, frontmatter: dict[str, Any], body: str
    ) -> SkillDef | None:
        """Parse skill definition from frontmatter (callback for discover_definitions)."""
        # Substitute template variables in body
        body = substitute_template(body, get_template_variables(self.config))

        try:
            return SkillDef(
                id=def_id,
                name=frontmatter["name"],  # type: ignore[misc]
                description=frontmatter["description"],  # type: ignore[misc]
                content=body.strip(),
            )
        except ValidationError as e:
            logger.warning(f"Invalid skill '{def_id}': {e}")
            return None

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
