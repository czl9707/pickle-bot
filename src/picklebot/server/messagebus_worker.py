"""MessageBus worker for ingesting platform messages."""

import asyncio
from typing import TYPE_CHECKING, Any

from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode, Agent
from picklebot.frontend.messagebus import MessageBusFrontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, dispatches to agent queue."""

    def __init__(
        self,
        context: "SharedContext",
        agent_queue: asyncio.Queue[Job],
        buses: list["MessageBus"],
    ):
        super().__init__(context)
        self.agent_queue = agent_queue
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Create global session on startup
        agent_def = context.agent_loader.load(context.config.default_agent)
        agent = Agent(agent_def, context)
        self.global_session = agent.new_session(SessionMode.CHAT)

    async def run(self) -> None:
        """Start all buses and process incoming messages."""
        self.logger.info(f"MessageBusWorker started with {len(self.buses)} bus(es)")

        bus_tasks = [
            bus.start(self._create_callback(bus.platform_name)) for bus in self.buses
        ]

        try:
            await asyncio.gather(*bus_tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    def _create_callback(self, platform: str):
        """Create callback for a specific platform."""

        async def callback(message: str, context: Any) -> None:
            bus = self.bus_map[platform]

            if not bus.is_allowed(context):
                self.logger.info(f"Ignored non-whitelisted message from {platform}")
                return

            # Create frontend for this message
            frontend = MessageBusFrontend(bus, context)

            # Dispatch job to agent queue
            job = Job(
                session_id=self.global_session.session_id,
                agent_id=self.global_session.agent_id,
                message=message,
                frontend=frontend,
                mode=SessionMode.CHAT,
            )
            await self.agent_queue.put(job)
            self.logger.debug(f"Dispatched message from {platform}")

        return callback
