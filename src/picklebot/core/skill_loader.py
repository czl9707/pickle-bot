"""Skill loader for discovering and loading skills."""

import logging
from pathlib import Path
from typing import Optional

import yaml

from picklebot.core.skill_def import SkillDef, SkillMetadata

logger = logging.getLogger(__name__)

class SkillNotFoundError(Exception):
    """Raised when a skill is not found."""

    pass


class SkillLoader:
    """Load and manage skill definitions from filesystem."""

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path

    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory and return list of valid SkillMetadata."""
        if not self.skills_path.exists():
            logger.warning(f"Skills directory not found: {self.skills_path}")
            return []

        skills = []
        for skill_dir in self.skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                logger.warning(f"No SKILL.md found in {skill_dir.name}")
                continue

            metadata = self._parse_skill_metadata(skill_file)
            if metadata:
                skills.append(metadata)

        return skills

    def _parse_skill_metadata(self, skill_file: Path) -> Optional[SkillMetadata]:
        """Parse skill metadata from SKILL.md file."""
        try:
            content = skill_file.read_text()

            # Split frontmatter and body
            if not content.startswith("---"):
                logger.warning(f"No frontmatter in {skill_file}")
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                logger.warning(f"Invalid frontmatter format in {skill_file}")
                return None

            frontmatter_str = parts[1].strip()
            frontmatter = yaml.safe_load(frontmatter_str)

            # Validate required fields
            if "name" not in frontmatter or "description" not in frontmatter:
                logger.warning(f"Missing required fields in {skill_file}")
                return None

            skill_id = skill_file.parent.name
            return SkillMetadata(
                id=skill_id,
                name=frontmatter["name"],
                description=frontmatter["description"],
            )
        except Exception as e:
            logger.warning(f"Failed to parse skill {skill_file}: {e}")
            return None

    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill definition by ID.

        Args:
            skill_id: The skill directory name

        Returns:
            SkillDef with full content

        Raises:
            SkillNotFoundError: If skill doesn't exist or is invalid
        """
        skill_dir = self.skills_path / skill_id
        if not skill_dir.exists() or not skill_dir.is_dir():
            raise SkillNotFoundError(f"Skill '{skill_id}' not found")

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise SkillNotFoundError(f"Skill '{skill_id}' has no SKILL.md")

        try:
            content = skill_file.read_text()

            # Split frontmatter and body
            if not content.startswith("---"):
                raise SkillNotFoundError(f"Skill '{skill_id}' has invalid format")

            parts = content.split("---", 2)
            if len(parts) < 3:
                raise SkillNotFoundError(f"Skill '{skill_id}' has invalid format")

            frontmatter_str = parts[1].strip()
            frontmatter = yaml.safe_load(frontmatter_str)
            body = parts[2].strip()

            # Validate required fields
            if "name" not in frontmatter or "description" not in frontmatter:
                raise SkillNotFoundError(f"Skill '{skill_id}' missing required fields")

            return SkillDef(
                id=skill_id,
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=body,
            )
        except SkillNotFoundError:
            raise
        except Exception as e:
            raise SkillNotFoundError(f"Failed to load skill '{skill_id}': {e}")
