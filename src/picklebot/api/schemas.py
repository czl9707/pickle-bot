"""Pydantic schemas for API request/response models."""

from typing import Any

from pydantic import BaseModel, create_model

from picklebot.core.cron_loader import CronDef
from picklebot.core.skill_loader import SkillDef


def make_create_model(model_cls: type[BaseModel], exclude: set[str]) -> type[BaseModel]:
    """Derive a Create model from existing model, excluding specified fields."""
    fields: dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        if name in exclude:
            continue
        # Use is_required() to check if field has a default
        if field.is_required():
            fields[name] = (field.annotation, ...)
        else:
            fields[name] = (field.annotation, field.default)

    return create_model(f"{model_cls.__name__}Create", **fields)


# Derived models - reuse existing definitions
# Note: These are created at runtime, so we use type: ignore for mypy
SkillCreate: type[BaseModel] = make_create_model(SkillDef, exclude={"id"})  # type: ignore[assignment]
CronCreate: type[BaseModel] = make_create_model(CronDef, exclude={"id"})  # type: ignore[assignment]


# Hand-written models (need special handling)


class MemoryCreate(BaseModel):
    """Request body for creating/updating a memory."""

    content: str


class AgentCreate(BaseModel):
    """Request body for creating/updating an agent."""

    name: str
    description: str = ""
    system_prompt: str
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    allow_skills: bool = False


class ConfigUpdate(BaseModel):
    """Request body for updating config (partial updates)."""

    default_agent: str | None = None
    chat_max_history: int | None = None
    job_max_history: int | None = None
