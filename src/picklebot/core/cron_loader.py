"""Cron job definition loader."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from datetime import datetime

from croniter import croniter
from pydantic import BaseModel, field_validator

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from picklebot.utils.config import Config

logger = logging.getLogger(__name__)

# Backward-compatible error aliases
CronNotFoundError = DefNotFoundError
InvalidCronError = InvalidDefError


class CronMetadata(BaseModel):
    """Lightweight cron info for discovery."""

    id: str
    name: str
    agent: str
    schedule: str


class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    agent: str
    schedule: str
    prompt: str

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: str) -> str:
        """Validate cron expression and enforce 5-minute minimum granularity."""
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")

        # Check minimum 5-minute granularity using croniter
        # Get the first two run times and check the gap

        base = datetime(2024, 1, 1, 0, 0)  # Arbitrary base time
        cron = croniter(v, base)
        first_run = cron.get_next(datetime)
        second_run = cron.get_next(datetime)
        gap_minutes = (second_run - first_run).total_seconds() / 60

        if gap_minutes < 5:
            raise ValueError(
                f"Schedule must have minimum 5-minute granularity. Got: {v} (runs every {gap_minutes:.0f} min)"
            )

        return v


class CronLoader:
    """Loads cron job definitions from CRON.md files."""

    @staticmethod
    def from_config(config: "Config") -> "CronLoader":
        """Create CronLoader from config."""
        return CronLoader(config.crons_path)

    def __init__(self, crons_path: Path):
        """
        Initialize CronLoader.

        Args:
            crons_path: Directory containing cron folders
        """
        self.crons_path = crons_path

    def discover_crons(self) -> list[CronMetadata]:
        """
        Scan crons directory, return lightweight metadata for all valid jobs.

        Returns:
            List of CronMetadata for valid cron jobs.
        """
        return discover_definitions(
            self.crons_path, "CRON.md", self._parse_cron_metadata, logger
        )

    def _parse_cron_metadata(
        self, def_id: str, frontmatter: dict, body: str
    ) -> CronMetadata | None:
        """
        Parse cron file and return metadata only.

        Args:
            def_id: Cron ID (folder name)
            frontmatter: Parsed frontmatter dict
            body: Markdown body content

        Returns:
            CronMetadata instance or None on validation failure
        """
        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise ValueError(f"missing required field: {field}")

        return CronMetadata(
            id=def_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
        )

    def load(self, cron_id: str) -> CronDef:
        """
        Load cron by ID.

        Args:
            cron_id: Cron folder name

        Returns:
            CronDef with full definition

        Raises:
            CronNotFoundError: Cron folder or file doesn't exist
            InvalidCronError: Cron file is malformed
        """
        cron_file = self.crons_path / cron_id / "CRON.md"
        if not cron_file.exists():
            raise DefNotFoundError("cron", cron_id)

        try:
            content = cron_file.read_text()
            frontmatter, body = parse_frontmatter(content, lambda d: d)
        except Exception as e:
            raise InvalidDefError("cron", cron_id, str(e))

        # Validate required fields
        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise InvalidDefError("cron", cron_id, f"missing required field: {field}")

        # Validate schedule via the field validator
        try:
            CronDef.validate_schedule(frontmatter["schedule"])
        except ValueError as e:
            raise InvalidDefError("cron", cron_id, str(e))

        return CronDef(
            id=cron_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
            prompt=body.strip(),
        )
