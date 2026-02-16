"""Skill loader for discovering and loading skills."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from picklebot.utils.config import Config

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
SkillNotFoundError = DefNotFoundError


class SkillMetadata(BaseModel):
    """Lightweight skill info for discovery."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str


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

    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory and return list of valid SkillMetadata."""
        return discover_definitions(
            self.skills_path, "SKILL.md", self._parse_skill_metadata, logger
        )

    def _parse_skill_metadata(
        self, def_id: str, frontmatter: dict[str, Any], body: str
    ) -> Optional[SkillMetadata]:
        """Parse skill metadata from frontmatter (callback for discover_definitions)."""
        # Validate required fields
        if "name" not in frontmatter or "description" not in frontmatter:
            logger.warning(f"Missing required fields in skill '{def_id}'")
            return None

        return SkillMetadata(
            id=def_id,
            name=frontmatter["name"],
            description=frontmatter["description"],
        )

    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill definition by ID.

        Args:
            skill_id: The skill directory name

        Returns:
            SkillDef with full content

        Raises:
            SkillNotFoundError: If skill doesn't exist
            InvalidDefError: If skill is invalid (malformed, missing fields)
        """
        skill_dir = self.skills_path / skill_id
        if not skill_dir.exists() or not skill_dir.is_dir():
            raise DefNotFoundError("skill", skill_id)

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise DefNotFoundError("skill", skill_id)

        content = skill_file.read_text()
        frontmatter, body = parse_frontmatter(content)

        # Check if frontmatter was parsed
        if not frontmatter:
            raise InvalidDefError("skill", skill_id, "no valid frontmatter")

        # Validate required fields
        if "name" not in frontmatter or "description" not in frontmatter:
            raise InvalidDefError("skill", skill_id, "missing required fields")

        return SkillDef(
            id=skill_id,
            name=frontmatter["name"],
            description=frontmatter["description"],
            content=body.strip(),
        )
