"""MessageBus worker for ingesting platform messages."""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from picklebot.server.base import Worker
from picklebot.core.agent import SessionMode, Agent
from picklebot.events.types import Event, EventType
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

        # Load default agent for session creation
        try:
            self.agent_def = context.agent_loader.load(context.config.default_agent)
            self.agent = Agent(self.agent_def, context)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {context.config.default_agent}")
            raise RuntimeError(f"Failed to initialize MessageBusWorker: {e}") from e

    def _get_or_create_session_id(self, platform: str, user_id: str) -> str:
        """Get existing session_id or create new session for this user."""
        # CLI sessions are stored in an instance attribute (simple dict)
        if platform == "cli":
            if not hasattr(self.context.config, "_cli_sessions"):
                self.context.config._cli_sessions = {}
            session_id = self.context.config._cli_sessions.get(user_id)
            if session_id:
                return session_id
        else:
            # Other platforms use typed config
            platform_config = getattr(self.context.config.messagebus, platform, None)
            if platform_config:
                session_id = platform_config.sessions.get(user_id)
                if session_id:
                    return session_id

        # No existing session - create new (creates in HistoryStore)
        session = self.agent.new_session(SessionMode.CHAT)

        # Persist session_id
        if platform == "cli":
            if not hasattr(self.context.config, "_cli_sessions"):
                self.context.config._cli_sessions = {}
            self.context.config._cli_sessions[user_id] = session.session_id
        else:
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

                # Build source and metadata
                source = f"{platform}:{user_id}"
                metadata = self._extract_metadata(context)

                # Publish INBOUND event
                event = Event(
                    type=EventType.INBOUND,
                    session_id=session_id,
                    content=message,
                    source=source,
                    timestamp=time.time(),
                    metadata=metadata,
                )
                await self.context.eventbus.publish(event)
                self.logger.debug(f"Published INBOUND event from {source}")

            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback

    def _extract_metadata(self, context: Any) -> dict[str, Any]:
        """Extract platform-specific metadata from context."""
        metadata = {}

        # Extract common fields if they exist
        if hasattr(context, "chat_id"):
            metadata["chat_id"] = context.chat_id
        if hasattr(context, "channel_id"):
            metadata["channel_id"] = context.channel_id

        return metadata
