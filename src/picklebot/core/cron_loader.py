"""Cron job definition loader."""

import logging
from pathlib import Path
from typing import Any

import yaml
from croniter import croniter
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


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
        from datetime import datetime

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


class CronNotFoundError(Exception):
    """Cron folder or CRON.md doesn't exist."""

    def __init__(self, cron_id: str):
        super().__init__(f"Cron job not found: {cron_id}")
        self.cron_id = cron_id


class InvalidCronError(Exception):
    """Cron file is malformed."""

    def __init__(self, cron_id: str, reason: str):
        super().__init__(f"Invalid cron job '{cron_id}': {reason}")
        self.cron_id = cron_id
        self.reason = reason


class CronLoader:
    """Loads cron job definitions from CRON.md files."""

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
        if not self.crons_path.exists():
            logger.warning(f"Crons directory not found: {self.crons_path}")
            return []

        crons = []
        for cron_dir in self.crons_path.iterdir():
            if not cron_dir.is_dir():
                continue

            cron_file = cron_dir / "CRON.md"
            if not cron_file.exists():
                logger.warning(f"No CRON.md found in {cron_dir.name}")
                continue

            try:
                metadata = self._parse_cron_metadata(cron_file)
                crons.append(metadata)
            except Exception as e:
                logger.warning(f"Invalid cron {cron_dir.name}: {e}")
                continue

        return crons

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
            raise CronNotFoundError(cron_id)

        try:
            frontmatter, body = self._parse_cron_file(cron_file)
        except Exception as e:
            raise InvalidCronError(cron_id, str(e))

        # Validate required fields
        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise InvalidCronError(cron_id, f"missing required field: {field}")

        # Validate schedule via the field validator
        try:
            CronDef.validate_schedule(frontmatter["schedule"])
        except ValueError as e:
            raise InvalidCronError(cron_id, str(e))

        return CronDef(
            id=cron_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
            prompt=body.strip(),
        )

    def _parse_cron_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter + markdown body.

        Args:
            path: Path to CRON.md file

        Returns:
            Tuple of (frontmatter dict, body string)
        """
        content = path.read_text()
        parts = [p for p in content.split("---\n") if p.strip()]

        if len(parts) < 2:
            return {}, content

        frontmatter_text = parts[0]
        body = "---\n".join(parts[1:])

        frontmatter = yaml.safe_load(frontmatter_text) or {}
        return frontmatter, body

    def _parse_cron_metadata(self, path: Path) -> CronMetadata:
        """
        Parse cron file and return metadata only.

        Args:
            path: Path to CRON.md file

        Returns:
            CronMetadata instance
        """
        frontmatter, _ = self._parse_cron_file(path)

        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise ValueError(f"missing required field: {field}")

        return CronMetadata(
            id=path.parent.name,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
        )
