"""Agent resource router."""

import shutil

from fastapi import APIRouter, Depends, HTTPException, status

from picklebot.api.deps import get_context
from picklebot.api.schemas import AgentCreate
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.def_loader import DefNotFoundError, write_definition

router = APIRouter()


def _write_agent_file(agent_id: str, data: AgentCreate, agents_path) -> None:
    """Write agent definition to file."""
    frontmatter = {
        "name": data.name,
        "description": data.description,
        "temperature": data.temperature,
        "max_tokens": data.max_tokens,
        "allow_skills": data.allow_skills,
    }
    if data.provider:
        frontmatter["provider"] = data.provider
    if data.model:
        frontmatter["model"] = data.model

    write_definition(agent_id, frontmatter, data.system_prompt, agents_path, "AGENT.md")


@router.get("", response_model=list[AgentDef])
def list_agents(ctx: SharedContext = Depends(get_context)) -> list[AgentDef]:
    """List all agents."""
    return ctx.agent_loader.discover_agents()


@router.get("/{agent_id}", response_model=AgentDef)
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> AgentDef:
    """Get agent by ID."""
    try:
        return ctx.agent_loader.load(agent_id)
    except DefNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


@router.post(
    "/{agent_id}", response_model=AgentDef, status_code=status.HTTP_201_CREATED
)
def create_agent(
    agent_id: str, data: AgentCreate, ctx: SharedContext = Depends(get_context)
) -> AgentDef:
    """Create a new agent."""
    agents_path = ctx.config.agents_path
    agent_file = agents_path / agent_id / "AGENT.md"

    if agent_file.exists():
        raise HTTPException(status_code=409, detail=f"Agent already exists: {agent_id}")

    _write_agent_file(agent_id, data, agents_path)
    return ctx.agent_loader.load(agent_id)


@router.put("/{agent_id}", response_model=AgentDef)
def update_agent(
    agent_id: str, data: AgentCreate, ctx: SharedContext = Depends(get_context)
) -> AgentDef:
    """Update an existing agent."""
    agents_path = ctx.config.agents_path
    agent_file = agents_path / agent_id / "AGENT.md"

    if not agent_file.exists():
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    _write_agent_file(agent_id, data, agents_path)
    return ctx.agent_loader.load(agent_id)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete an agent."""
    agents_path = ctx.config.agents_path
    agent_dir = agents_path / agent_id

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    shutil.rmtree(agent_dir)
