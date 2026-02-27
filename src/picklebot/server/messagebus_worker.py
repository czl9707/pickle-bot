"""MessageBus worker for ingesting platform messages."""

import asyncio
from typing import TYPE_CHECKING, Any

from picklebot.frontend.base import Frontend
from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode, Agent
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, dispatches to agent queue."""

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
        """Get existing session_id or create new session for this user.

        For CLI platform, always creates a new session (no persistence needed).
        """
        # CLI doesn't need session persistence - just create a new session each time
        if platform == "cli":
            session = self.agent.new_session(SessionMode.CHAT)
            return session.session_id

        platform_config = getattr(self.context.config.messagebus, platform, None)
        if not platform_config:
            raise ValueError(f"No config for platform: {platform}")

        session_id = platform_config.sessions.get(user_id)

        if session_id:
            return session_id

        # No session - create new (creates in HistoryStore)
        session = self.agent.new_session(SessionMode.CHAT)

        # Persist session_id to runtime config
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

                # Get or create session for this user
                session_id = self._get_or_create_session_id(platform, user_id)

                frontend = Frontend.for_bus(bus, context)

                # For CLI, create a future so we can wait for completion
                # This ensures the prompt doesn't appear before the response
                result_future: asyncio.Future[str] | None = None
                if platform == "cli":
                    result_future = asyncio.get_event_loop().create_future()

                job = Job(
                    session_id=session_id,
                    agent_id=self.agent_def.id,
                    message=message,
                    frontend=frontend,
                    mode=SessionMode.CHAT,
                    result_future=result_future,
                )
                await self.context.agent_queue.put(job)
                self.logger.debug(f"Dispatched message from {platform}")

                # For CLI, wait for the job to complete before returning
                # This gives a synchronous feel - prompt appears after response
                if platform == "cli" and result_future:
                    await result_future
            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
