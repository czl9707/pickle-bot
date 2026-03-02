"""MessageBus worker for ingesting platform messages."""

import asyncio
import time
from typing import TYPE_CHECKING

from .worker import Worker
from picklebot.core.agent import Agent
from picklebot.core.events import EventSource, InboundEvent

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

    def _get_or_create_session_id(self, source: str, agent_id: str) -> str:
        """Get existing session_id from source cache, or create new session."""
        # Check source cache
        source_info = self.context.config.sources.get(source)
        if source_info:
            return source_info["session_id"]

        # Create new session
        agent_def = self.context.agent_loader.load(agent_id)
        agent = Agent(agent_def, self.context)
        session = agent.new_session(source)

        # Update source cache
        self.context.config.set_runtime(
            f"sources.{source}", {"session_id": session.session_id}
        )
        return session.session_id

    async def run(self) -> None:
        """Start all buses and process incoming messages."""
        self.logger.info(f"MessageBusWorker started with {len(self.buses)} bus(es)")

        bus_tasks = [
            bus.run(self._create_callback(bus.platform_name)) for bus in self.buses
        ]

        try:
            await asyncio.gather(*bus_tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    def _create_callback(self, platform: str):
        """Create callback for a specific platform."""

        async def callback(message: str, source: EventSource) -> None:
            try:
                bus = self.bus_map[platform]

                if not bus.is_allowed(source):
                    self.logger.debug(
                        f"Ignored non-whitelisted message from {platform}"
                    )
                    return

                # Check for slash command
                if message.startswith("/"):
                    self.logger.debug(f"Processing slash command from {platform}")
                    result = self.context.command_registry.dispatch(
                        message, self.context
                    )
                    if result:
                        await bus.reply(result, source)
                    return

                # Use str(source) for routing/session lookup
                source_str = str(source)
                agent_id = self.context.routing_table.resolve(source_str)

                if not agent_id:
                    self.logger.debug(f"No routing match for {source_str}")
                    return

                session_id = self._get_or_create_session_id(source_str, agent_id)

                # Publish INBOUND event with typed source
                event = InboundEvent(
                    session_id=session_id,
                    agent_id=agent_id,
                    source=source,
                    content=message,
                    timestamp=time.time(),
                )
                await self.context.eventbus.publish(event)
                self.logger.debug(f"Published INBOUND event from {source_str}")

            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
