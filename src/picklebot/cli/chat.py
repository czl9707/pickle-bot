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
from picklebot.server.agent_worker import AgentDispatcherWorker
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

        # Create single CLI session for this conversation
        # Store in config instance attribute so MessageBusWorker can reuse it
        self.cli_session_id = str(uuid.uuid4())
        self.context.config._cli_sessions = {"cli-user": self.cli_session_id}

        # Create workers
        self.dispatcher = AgentDispatcherWorker(self.context)
        self.messagebus_worker = MessageBusWorker(self.context)

        # Create DeliveryWorker for handling OUTBOUND events
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

        # Subscribe DeliveryWorker to handle OUTBOUND events (prints to CLI)
        self.delivery_worker.subscribe(self.context.eventbus)

        # Subscribe AgentDispatcherWorker to handle INBOUND events
        self.dispatcher.subscribe(self.context.eventbus)

        try:
            # Run workers concurrently
            # - MessageBusWorker: reads input, publishes INBOUND events
            # - AgentDispatcherWorker: processes INBOUND events + job queue
            # - DeliveryWorker handles OUTBOUND events via subscription (not a task)
            await asyncio.gather(
                self.dispatcher.run(),
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
