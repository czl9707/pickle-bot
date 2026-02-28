"""MessageBus worker for ingesting platform messages."""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from .worker import Worker
from picklebot.core.agent import SessionMode, Agent
from picklebot.core.events import InboundEvent, Source
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

        # CLI session ID (CLI only has one session per worker)
        self._cli_session_id: str | None = None

        # Load default agent for session creation
        try:
            self.agent_def = context.agent_loader.load(context.config.default_agent)
            self.agent = Agent(self.agent_def, context)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {context.config.default_agent}")
            raise RuntimeError(f"Failed to initialize MessageBusWorker: {e}") from e

    def _get_or_create_session_id(self, platform: str, user_id: str) -> str:
        """Get existing session_id or create new session for this user."""
        # CLI has a single session stored in the worker
        if platform == "cli":
            if not self._cli_session_id:
                session = self.agent.new_session(SessionMode.CHAT)
                self._cli_session_id = session.session_id
            return session.session_id

        # Other platforms use typed config
        platform_config = getattr(self.context.config.messagebus, platform, None)
        if platform_config:
            session_id = platform_config.sessions.get(user_id)
            if session_id:
                return session_id

        # No existing session - create new
        session = self.agent.new_session(SessionMode.CHAT)
        self.context.config.set_runtime(
            f"messagebus.{platform}.sessions.{user_id}", session.session_id
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

        async def callback(message: str, context: Any) -> None:
            try:
                bus = self.bus_map[platform]

                if not bus.is_allowed(context):
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
                        await bus.reply(result, context)
                    return

                # Extract user_id from context
                user_id = context.user_id
                session_id = self._get_or_create_session_id(platform, user_id)

                # Publish INBOUND event with typed context
                event = InboundEvent(
                    session_id=session_id,
                    agent_id=self.context.config.default_agent,
                    source=Source.platform(platform, user_id),
                    content=message,
                    timestamp=time.time(),
                    context=context,
                )
                await self.context.eventbus.publish(event)
                self.logger.debug(f"Published INBOUND event from {event.source}")

            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
