"""Post message tool factory for agent-initiated messaging."""

import time
from typing import TYPE_CHECKING

from picklebot.core.events import AgentEventSource, OutboundEvent
from picklebot.tools.base import BaseTool, tool

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession
    from picklebot.core.context import SharedContext


def create_post_message_tool(context: "SharedContext") -> BaseTool | None:
    """
    Factory to create post_message tool.

    Args:
        context: SharedContext with messagebus configuration

    Returns:
        Tool for posting messages, or None if messagebus not enabled
    """
    config = context.config

    # Return None if messagebus not enabled or no buses configured
    if not config.channels.enabled:
        return None

    # Check if we have any buses configured
    if not context.channels:
        return None

    @tool(
        name="post_message",
        description="Send a message to the user via the default messaging platform. Use this to proactively notify the user about completed tasks, cron results, or important updates.",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send to the user",
                }
            },
            "required": ["content"],
        },
    )
    async def post_message(content: str, session: "AgentSession") -> str:
        """
        Send a message to the default user on the default platform.

        Args:
            content: Message content to send
            session: The agent session context

        Returns:
            Success or error message
        """
        try:
            # Publish OUTBOUND event for the DeliveryWorker to handle
            event = OutboundEvent(
                session_id=session.session_id,
                agent_id=session.agent_id,
                source=AgentEventSource(agent_id=session.agent_id),
                content=content,
                timestamp=time.time(),
            )
            await context.eventbus.publish(event)
            return "Message queued for delivery"
        except Exception as e:
            return f"Failed to send message: {e}"

    return post_message
