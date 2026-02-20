"""Subagent dispatch tool factory for creating dynamic dispatch tool."""

import json
from typing import TYPE_CHECKING

from picklebot.frontend.base import SilentFrontend
from picklebot.tools.base import BaseTool, tool
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.frontend import Frontend


def create_subagent_dispatch_tool(
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

    # Discover available agents, exclude current
    shared_context = context
    available_agents = shared_context.agent_loader.discover_agents()
    dispatchable_agents = [a for a in available_agents if a.id != current_agent_id]

    if not dispatchable_agents:
        return None

    # Build description listing available agents
    agents_desc = "<available_agents>\n"
    for agent_def in dispatchable_agents:
        agents_desc += f'  <agent id="{agent_def.id}">{agent_def.description}</agent>\n'
    agents_desc += "</available_agents>"

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
    async def subagent_dispatch(
        frontend: "Frontend", agent_id: str, task: str, context: str = ""
    ) -> str:
        """Dispatch task to subagent, return result + session_id.

        Args:
            frontend: Frontend for displaying dispatch status
            agent_id: ID of the target agent
            task: Task for the subagent to perform
            context: Optional context information

        Returns:
            JSON with result and session_id
        """
        # Import here to avoid circular dependency
        from picklebot.core.agent import Agent, SessionMode

        try:
            target_def = shared_context.agent_loader.load(agent_id)
        except DefNotFoundError:
            raise ValueError(f"Agent '{agent_id}' not found")

        subagent = Agent(target_def, shared_context)

        user_message = task
        if context:
            user_message = f"{task}\n\nContext:\n{context}"

        async with frontend.show_dispatch(current_agent_id, agent_id, task):
            session = subagent.new_session(SessionMode.JOB)
            # Might need revisit this piece later to find out a more flexible way of communicating with ouside.
            response = await session.chat(user_message, SilentFrontend())

        result = {
            "result": response,
            "session_id": session.session_id,
        }
        return json.dumps(result)

    return subagent_dispatch
