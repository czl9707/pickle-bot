"""Chat CLI command for interactive sessions."""

import asyncio
import logging
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.context import SharedContext
from picklebot.events.delivery import DeliveryWorker
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcher
from picklebot.server.messagebus_worker import MessageBusWorker
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
        
        # Create workers
        self.dispatcher = AgentDispatcher(self.context)
        self.messagebus_worker = MessageBusWorker(self.context)
        self.delivery_worker = DeliveryWorker(self.context)

    async def run(self) -> None:
        """Run the interactive chat loop with event-driven architecture."""
        # Display welcome message
        self.console.print(
            Panel(
                Text("Welcome to pickle-bot!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

        self.delivery_worker.subscribe(self.context.eventbus)
        self.dispatcher.subscribe()

        try:
            # Run workers concurrently
            # - MessageBusWorker: reads input, publishes INBOUND events
            # - AgentDispatcher: processes INBOUND events + job queue
            # - DeliveryWorker handles OUTBOUND events via subscription (not a task)
            await asyncio.gather(
                self.context.eventbus.run(),
                self.messagebus_worker.run(),
            )
        except asyncio.CancelledError:
            # Handle graceful shutdown
            self.console.print("\nGoodbye!")
            raise


def chat_command(ctx: typer.Context) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config)
    asyncio.run(chat_loop.run())
