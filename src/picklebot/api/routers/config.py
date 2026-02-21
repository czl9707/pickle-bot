"""Config resource router."""

import yaml

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.api.schemas import ConfigUpdate
from picklebot.core.context import SharedContext

router = APIRouter()


class ConfigResponse(BaseModel):
    """Response model for config (excludes sensitive fields)."""

    default_agent: str
    chat_max_history: int
    job_max_history: int


@router.get("", response_model=ConfigResponse)
def get_config(ctx: SharedContext = Depends(get_context)) -> dict:
    """Get current config."""
    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
    }


@router.patch("", response_model=ConfigResponse)
def update_config(
    data: ConfigUpdate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Update config fields."""
    user_config_path = ctx.config.workspace / "config.user.yaml"

    # Load existing user config or start fresh
    if user_config_path.exists():
        with open(user_config_path) as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    # Apply updates
    if data.default_agent is not None:
        user_config["default_agent"] = data.default_agent
    if data.chat_max_history is not None:
        user_config["chat_max_history"] = data.chat_max_history
    if data.job_max_history is not None:
        user_config["job_max_history"] = data.job_max_history

    # Write back
    with open(user_config_path, "w") as f:
        yaml.dump(user_config, f)

    return {
        "default_agent": data.default_agent or ctx.config.default_agent,
        "chat_max_history": data.chat_max_history or ctx.config.chat_max_history,
        "job_max_history": data.job_max_history or ctx.config.job_max_history,
    }
