"""Skill definition models."""

from pydantic import BaseModel, ConfigDict


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
