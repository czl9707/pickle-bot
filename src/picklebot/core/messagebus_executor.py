"""Message bus executor for handling platform messages."""

import asyncio
import logging
from typing import Any, Callable, Awaitable

from picklebot.core.context import SharedContext
from picklebot.core.agent import Agent
from picklebot.messagebus.base import MessageBus
from picklebot.frontend.base import SilentFrontend

logger = logging.getLogger(__name__)


class MessageBusExecutor:
    """Orchestrates message flow between platforms and agent."""

    def __init__(self, context: SharedContext, buses: list[MessageBus[Any]]):
        """
        Initialize MessageBusExecutor.

        Args:
            context: Shared application context
            buses: List of message bus implementations
        """
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Single shared session for all platforms
        agent_def = context.agent_loader.load(context.config.default_agent)
        agent = Agent(agent_def=agent_def, context=context)
        self.session = agent.new_session()

        # Message queue for sequential processing
        # Stores (message, platform, context) - context is platform-specific
        self.message_queue: asyncio.Queue[tuple[str, str, Any]] = asyncio.Queue()
        self.frontend = SilentFrontend()

    async def run(self) -> None:
        """Start message processing loop and all buses."""
        logger.info("MessageBusExecutor started")

        worker_task = asyncio.create_task(self._process_messages())
        # Create wrapper callbacks that add platform identifier
        bus_tasks = [
            bus.start(self._create_callback(bus.platform_name)) for bus in self.buses
        ]

        try:
            await asyncio.gather(worker_task, *bus_tasks)
        except asyncio.CancelledError:
            logger.info("MessageBusExecutor shutting down...")
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    def _create_callback(self, platform: str) -> Callable[[str, Any], Awaitable[None]]:
        """
        Create a callback wrapper for a specific platform.

        Args:
            platform: Platform identifier

        Returns:
            Async callback function that enqueues messages with platform info
        """

        async def callback(message: str, context: Any) -> None:
            await self._enqueue_message(message, platform, context)

        return callback

    async def _enqueue_message(self, message: str, platform: str, context: Any) -> None:
        """
        Add incoming message to queue (called by buses).

        Args:
            message: User message content
            platform: Platform identifier
            context: Platform-specific message context
        """
        bus = self.bus_map[platform]

        # Delegate whitelist check to bus
        if not bus.is_allowed(context):
            logger.info(f"Ignored message from non-whitelisted user on {platform}")
            return

        await self.message_queue.put((message, platform, context))
        logger.debug(f"Enqueued message from {platform}")

    async def _process_messages(self) -> None:
        """Worker that processes messages sequentially from queue."""
        while True:
            message, platform, context = await self.message_queue.get()

            logger.info(f"Processing message from {platform}")

            try:
                response = await self.session.chat(message, self.frontend)
                await self.bus_map[platform].reply(content=response, context=context)
                logger.info(f"Sent response to {platform}")
            except Exception as e:
                logger.error(f"Error processing message from {platform}: {e}")
                try:
                    await self.bus_map[platform].reply(
                        content="Sorry, I encountered an error processing your message.",
                        context=context,
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
            finally:
                self.message_queue.task_done()
