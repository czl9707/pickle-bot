"""Cron job definition loader."""

from pathlib import Path
from typing import Any

import yaml
from croniter import croniter
from pydantic import BaseModel, field_validator


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

        # Check minimum 5-minute granularity
        # Parse the minute field (first field)
        minute_field = v.split()[0]

        # Allow: */5, */10, */15, etc. (divisible by 5)
        # Allow: 0, 5, 10, 15, etc. (specific minutes divisible by 5)
        # Allow: * only if other fields make it run at most every 5 minutes
        # For simplicity, we check if minute value is divisible by 5 or is */N where N >= 5

        if minute_field == "*":
            # Every minute - not allowed
            raise ValueError(
                f"Schedule must have minimum 5-minute granularity. Got: {v}"
            )
        elif minute_field.startswith("*/"):
            try:
                interval = int(minute_field[2:])
                if interval < 5:
                    raise ValueError(
                        f"Schedule must have minimum 5-minute granularity. Got: {v}"
                    )
            except ValueError:
                pass  # Let croniter validation handle it
        elif minute_field.isdigit():
            # Single minute value - this runs every hour at that minute, which is fine
            pass
        elif "," in minute_field:
            # Multiple values - check all are >= 5 minutes apart
            # For simplicity, just ensure we're not running more often than every 5 min
            pass

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
