"""Subagent dispatch tool factory for creating dynamic dispatch tool."""

import json
from typing import TYPE_CHECKING

from picklebot.frontend.base import SilentFrontend
from picklebot.tools.base import BaseTool, tool
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.agent_loader import AgentLoader
    from picklebot.core.context import SharedContext


def create_subagent_dispatch_tool(
    agent_loader: "AgentLoader",
    current_agent_id: str,
    context: "SharedContext",
) -> BaseTool | None:
    """Factory to create subagent dispatch tool with dynamic schema.

    Args:
        agent_loader: AgentLoader instance for discovering and loading agents
        current_agent_id: ID of the calling agent (will be excluded from enum)
        context: SharedContext for creating subagents

    Returns:
        Async tool function for dispatching to subagents, or None if no agents available
    """
    # Store reference before it gets shadowed by inner function parameter
    shared_context = context

    # Discover available agents, exclude current
    available_agents = agent_loader.discover_agents()
    dispatchable_agents = [a for a in available_agents if a.id != current_agent_id]

    if not dispatchable_agents:
        return None

    # Build description listing available agents
    agents_desc = "<available_agents>\n"
    for agent_def in dispatchable_agents:
        agents_desc += f'  <agent id="{agent_def.id}">{agent_def.description}</agent>\n'
    agents_desc += "</available_agents>"

    # Build enum of dispatchable agent IDs
    dispatchable_ids = [a.id for a in dispatchable_agents]

    @tool(
        name="subagent_dispatch",
        description=f"Dispatch a task to a specialized subagent.\n{agents_desc}",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "enum": dispatchable_ids,
                    "description": "ID of the agent to dispatch to",
                },
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to perform",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context information for the subagent",
                },
            },
            "required": ["agent_id", "task"],
        },
    )
    async def subagent_dispatch(agent_id: str, task: str, context: str = "") -> str:
        """Dispatch task to subagent, return result + session_id."""
        # Import here to avoid circular dependency
        from picklebot.core.agent import Agent

        # Load target agent definition
        try:
            target_def = agent_loader.load(agent_id)
        except DefNotFoundError:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Create subagent instance
        subagent = Agent(target_def, shared_context)

        # Build initial message
        user_message = task
        if context:
            user_message = f"{task}\n\nContext:\n{context}"

        # Create new session and run with silent frontend
        session = subagent.new_session()
        response = await session.chat(user_message, SilentFrontend())

        # Return result + session_id as JSON
        result = {
            "result": response,
            "session_id": session.session_id,
        }
        return json.dumps(result)

    return subagent_dispatch
