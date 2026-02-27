"""Chat CLI command for interactive sessions."""

import asyncio

import typer

from picklebot.core import SharedContext
from picklebot.messagebus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging


class ChatLoop:
    """Interactive chat session using MessageBusWorker pattern."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        # Create CliBus and SharedContext with buses parameter
        self.bus = CliBus()
        self.context = SharedContext(config=config, buses=[self.bus])

        # Create workers (pass agent_id to MessageBusWorker)
        self.dispatcher = AgentDispatcherWorker(self.context)
        self.messagebus_worker = MessageBusWorker(self.context, agent_id=self.agent_id)

    async def run(self) -> None:
        """Run the interactive chat loop with MessageBusWorker + AgentDispatcherWorker."""
        # Show welcome message
        print("Welcome to PickleBot! Type 'quit', 'exit', or 'q' to exit.")

        try:
            # Run both workers concurrently
            await asyncio.gather(
                self.dispatcher.run(),
                self.messagebus_worker.run(),
            )
        except asyncio.CancelledError:
            # Handle graceful shutdown
            print("\nGoodbye!")
            raise


def chat_command(ctx: typer.Context, agent_id: str | None = None) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config, agent_id=agent_id)
    asyncio.run(chat_loop.run())
