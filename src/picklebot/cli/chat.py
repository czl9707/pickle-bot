"""Chat CLI command for interactive sessions."""

import asyncio

import typer

from picklebot.core.context import SharedContext
from picklebot.frontend.console import ConsoleFrontend
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging


class ChatLoop:
    """Interactive chat session using MessageBusWorker pattern."""

    def __init__(self, config: Config):
        self.config = config
        self.frontend = ConsoleFrontend()

        # Create CliBus and SharedContext with buses parameter
        self.bus = CliBus()
        self.context = SharedContext(config=config, buses=[self.bus])

        # Create workers (uses default agent)
        self.dispatcher = AgentDispatcherWorker(self.context)
        self.messagebus_worker = MessageBusWorker(self.context)

    async def run(self) -> None:
        """Run the interactive chat loop with MessageBusWorker + AgentDispatcherWorker."""
        await self.frontend.show_welcome()

        try:
            # Run both workers concurrently
            await asyncio.gather(
                self.dispatcher.run(),
                self.messagebus_worker.run(),
            )
        except asyncio.CancelledError:
            # Handle graceful shutdown
            await self.frontend.show_system_message("\nGoodbye!")
            raise


def chat_command(ctx: typer.Context) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config)
    asyncio.run(chat_loop.run())
