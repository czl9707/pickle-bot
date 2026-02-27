"""CLI message bus implementation."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

from rich.console import Console

from picklebot.messagebus.base import MessageBus, MessageContext

logger = logging.getLogger(__name__)


@dataclass
class CliContext(MessageContext):
    """Context for CLI messages."""

    user_id: str = "cli-user"


class CliBus(MessageBus[CliContext]):
    """CLI platform implementation using stdin/stdout."""

    platform_name = "cli"

    def __init__(self):
        """Initialize CliBus."""
        self.console = Console()
        self._stop_event = asyncio.Event()
        self._running = False

    def is_allowed(self, context: CliContext) -> bool:
        """Check if sender is whitelisted. CLI always allows all users."""
        return True

    async def run(
        self, on_message: Callable[[str, CliContext], Awaitable[None]]
    ) -> None:
        """Run the CLI message bus. Blocks until stop() is called or quit command.

        Raises:
            RuntimeError: If run() is called when already running.
        """
        if self._running:
            raise RuntimeError("CliBus already running")

        self._running = True
        self._stop_event.clear()  # Reset for this run
        logger.info(f"Message bus enabled with platform: {self.platform_name}")

        try:
            while not self._stop_event.is_set():
                # Read input in a thread to avoid blocking the event loop
                try:
                    user_input = await asyncio.to_thread(input, "You: ")

                    # Check for quit commands (case-insensitive)
                    if user_input.lower().strip() in ("quit", "exit", "q"):
                        logger.info("Quit command received, stopping CLI bus")
                        break

                    # Skip empty or whitespace-only input
                    if not user_input.strip():
                        continue

                    # Create context and call the message callback
                    ctx = CliContext()
                    logger.debug(f"Received CLI message from user {ctx.user_id}")

                    try:
                        await on_message(user_input, ctx)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")

                except EOFError:
                    # Handle Ctrl+D
                    logger.info("EOF received, stopping CLI bus")
                    break
                except KeyboardInterrupt:
                    # Handle Ctrl+C
                    logger.info("Keyboard interrupt received, stopping CLI bus")
                    break
        finally:
            self._running = False
            logger.info("CliBus stopped")

    async def reply(self, content: str, context: CliContext) -> None:
        """Reply to incoming message by printing to stdout."""
        self.console.print(content)
        logger.debug(f"Sent CLI reply to {context.user_id}")

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message to stdout. Target parameter is ignored."""
        # CLI has no concept of channels/targets, so we ignore target parameter
        self.console.print(content)
        logger.debug("Sent CLI post")

    async def stop(self) -> None:
        """Stop CLI bus and cleanup."""
        if not self._running:
            return
        logger.info("Stopping CliBus")
        self._stop_event.set()
        logger.info("CliBus stop signaled")
