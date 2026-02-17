"""Message bus executor for handling platform messages."""

import asyncio
import logging

from picklebot.core.context import SharedContext
from picklebot.core.agent import Agent
from picklebot.messagebus.base import MessageBus
from picklebot.frontend.base import SilentFrontend

logger = logging.getLogger(__name__)


class MessageBusExecutor:
    """Orchestrates message flow between platforms and agent."""

    def __init__(self, context: SharedContext, buses: list[MessageBus]):
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
        self.message_queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
        self.frontend = SilentFrontend()

    async def run(self) -> None:
        """Start message processing loop and all buses."""
        logger.info("MessageBusExecutor started")

        worker_task = asyncio.create_task(self._process_messages())
        bus_tasks = [bus.start(self._enqueue_message) for bus in self.buses]

        try:
            await asyncio.gather(worker_task, *bus_tasks)
        except asyncio.CancelledError:
            logger.info("MessageBusExecutor shutting down...")
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    async def _enqueue_message(
        self, message: str, platform: str, user_id: str
    ) -> None:
        """
        Add incoming message to queue (called by buses).

        Args:
            message: User message content
            platform: Platform identifier
            user_id: Platform-specific user ID
        """
        bus = self.bus_map[platform]

        # Check whitelist (empty list allows all)
        if (
            hasattr(bus, "config")
            and bus.config.allowed_user_ids
            and user_id not in bus.config.allowed_user_ids
        ):
            logger.info(f"Ignored message from non-whitelisted user {platform}/{user_id}")
            return

        await self.message_queue.put((message, platform, user_id))
        logger.debug(f"Enqueued message from {platform}/{user_id}")

    async def _process_messages(self) -> None:
        """Worker that processes messages sequentially from queue."""
        while True:
            message, platform, user_id = await self.message_queue.get()

            logger.info(f"Processing message from {platform}/{user_id}")

            try:
                response = await self.session.chat(message, self.frontend)
                await self.bus_map[platform].send_message(content=response, user_id=user_id)
                logger.info(f"Sent response to {platform}/{user_id}")
            except Exception as e:
                logger.error(f"Error processing message from {platform}: {e}")
                try:
                    await self.bus_map[platform].send_message(
                        content="Sorry, I encountered an error processing your message.",
                        user_id=user_id,
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
            finally:
                self.message_queue.task_done()
