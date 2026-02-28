"""Chat CLI command for interactive sessions."""

import asyncio
import logging

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server import AgentWorker, DeliveryWorker, MessageBusWorker, Worker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class ChatLoop:
    """Interactive chat session using event-driven architecture."""

    def __init__(self, config: Config):
        self.config = config
        self.console = Console()

        # Create CliBus and SharedContext with buses parameter
        self.bus = CliBus()
        self.context = SharedContext(config=config, buses=[self.bus])

        # Create ALL workers - same pattern as Server
        self.workers: list[Worker] = [
            self.context.eventbus,
            AgentWorker(self.context),
            DeliveryWorker(self.context),
            MessageBusWorker(self.context),
        ]

    async def run(self) -> None:
        """Run the interactive chat loop."""
        # Display welcome message
        self.console.print(
            Panel(
                Text("Welcome to pickle-bot!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

        # Start all workers
        for worker in self.workers:
            worker.start()

        try:
            # Wait forever - workers handle everything
            await asyncio.Future()
        except asyncio.CancelledError:
            self.console.print("\nGoodbye!")
            # Stop all workers gracefully
            for worker in self.workers:
                await worker.stop()
            raise


def chat_command(ctx: typer.Context) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config)
    asyncio.run(chat_loop.run())
