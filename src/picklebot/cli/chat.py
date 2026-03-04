"""Chat CLI command for interactive sessions."""

import asyncio
import logging
import warnings

# Suppress all warnings at module level (e.g., RequestsDependencyWarning)
warnings.filterwarnings("ignore")

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from picklebot.core.events import OutboundEvent  # noqa: E402
from picklebot.core.context import SharedContext  # noqa: E402
from picklebot.server import (  # noqa: E402
    AgentWorker,
    Worker,
)
from picklebot.utils.config import Config  # noqa: E402
from picklebot.utils.logging import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)


class ChatLoop:
    """Interactive chat session using event-driven architecture."""

    def __init__(self, config: Config):
        self.config = config
        self.console = Console()

        # Create SharedContext without buses
        self.context = SharedContext(config=config, buses=[])

        # Create minimal workers for CLI chat
        self.workers: list[Worker] = [
            self.context.eventbus,
            AgentWorker(self.context),
        ]

        # Response queue for collecting agent responses
        self.response_queue: asyncio.Queue[OutboundEvent] = asyncio.Queue()

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
