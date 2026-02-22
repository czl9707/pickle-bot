"""Config resource router."""

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
    max_history_file_size: int


@router.get("", response_model=ConfigResponse)
def get_config(ctx: SharedContext = Depends(get_context)) -> dict:
    """Get current config."""
    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
        "max_history_file_size": ctx.config.max_history_file_size,
    }


@router.patch("", response_model=ConfigResponse)
def update_config(
    data: ConfigUpdate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Update config fields."""
    if data.default_agent is not None:
        ctx.config.set_user("default_agent", data.default_agent)
    if data.chat_max_history is not None:
        ctx.config.set_user("chat_max_history", data.chat_max_history)
    if data.job_max_history is not None:
        ctx.config.set_user("job_max_history", data.job_max_history)
    if data.max_history_file_size is not None:
        ctx.config.set_user("max_history_file_size", data.max_history_file_size)

    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
        "max_history_file_size": ctx.config.max_history_file_size,
    }
