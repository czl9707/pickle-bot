"""Agent resource router."""

from fastapi import APIRouter, Depends, HTTPException

from picklebot.api.deps import get_context
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext

router = APIRouter()


@router.get("", response_model=list[AgentDef])
def list_agents(ctx: SharedContext = Depends(get_context)) -> list[AgentDef]:
    """List all agents."""
    return ctx.agent_loader.discover_agents()


@router.get("/{agent_id}", response_model=AgentDef)
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> AgentDef:
    """Get agent by ID."""
    try:
        return ctx.agent_loader.load(agent_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
