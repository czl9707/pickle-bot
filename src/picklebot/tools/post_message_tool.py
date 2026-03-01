"""Post message tool factory for agent-initiated messaging."""

import time
from typing import TYPE_CHECKING

from picklebot.core.events import OutboundEvent, Source
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

    # Return None if messagebus not enabled
    if not config.messagebus.enabled:
        return None

    # Get default platform
    default_platform = config.messagebus.default_platform
    if default_platform is None:
        return None

    # Verify the bus exists
    bus_map = {bus.platform_name: bus for bus in context.messagebus_buses}
    default_bus = bus_map.get(default_platform)

    if not default_bus:
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
                source=Source.agent(session.agent_id),
                content=content,
                timestamp=time.time(),
            )
            await context.eventbus.publish(event)
            return f"Message queued for delivery to {default_platform}"
        except Exception as e:
            return f"Failed to send message: {e}"

    return post_message
