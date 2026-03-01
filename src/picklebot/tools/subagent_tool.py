"""Subagent dispatch tool factory for creating dynamic dispatch tool."""

import asyncio
import json
import time
from typing import TYPE_CHECKING

from picklebot.core.events import DispatchEvent, DispatchResultEvent, Event, Source
from picklebot.tools.base import BaseTool, tool
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession
    from picklebot.core.context import SharedContext


def create_subagent_dispatch_tool(
    current_agent_id: str,
    context: "SharedContext",
) -> BaseTool | None:
    """Factory to create subagent dispatch tool with dynamic schema.

    Args:
        current_agent_id: ID of the calling agent (will be excluded from enum)
        context: SharedContext for event bus access

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
        agent_id: str, task: str, session: "AgentSession", context: str = ""
    ) -> str:
        """Dispatch task to subagent, return result + session_id.

        Args:
            agent_id: ID of the target agent
            task: Task for the subagent to perform
            session: The agent session context
            context: Optional context information

        Returns:
            JSON with result and session_id
        """
        # Verify agent exists and create session
        from picklebot.core.agent import Agent, SessionMode

        try:
            agent_def = shared_context.agent_loader.load(agent_id)
        except DefNotFoundError:
            raise ValueError(f"Agent '{agent_id}' not found")

        agent = Agent(agent_def, shared_context)
        agent_session = agent.new_session(SessionMode.JOB)
        session_id = agent_session.session_id

        user_message = task
        if context:
            user_message = f"{task}\n\nContext:\n{context}"

        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[str] = loop.create_future()

        # Create temp handler that filters by session_id
        async def handle_result(event: Event) -> None:
            if (
                isinstance(event, DispatchResultEvent)
                and event.session_id == session_id
            ):
                if not result_future.done():
                    if event.error:
                        result_future.set_exception(Exception(event.error))
                    else:
                        result_future.set_result(event.content)

        # Subscribe to DISPATCH_RESULT events
        from picklebot.core.events import EventType

        shared_context.eventbus.subscribe(EventType.DISPATCH_RESULT, handle_result)

        try:
            # Publish DISPATCH event
            event = DispatchEvent(
                session_id=session_id,
                agent_id=agent_id,
                source=Source.agent(current_agent_id),
                content=user_message,
                timestamp=time.time(),
                parent_session_id=session.session_id,
            )
            await shared_context.eventbus.publish(event)

            # Wait for result
            response = await result_future
        finally:
            # Always unsubscribe
            shared_context.eventbus.unsubscribe(handle_result)

        result = {"result": response, "session_id": session_id}
        return json.dumps(result)

    return subagent_dispatch
