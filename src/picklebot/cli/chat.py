"""Chat CLI command for interactive sessions."""

import asyncio
import logging
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent import SessionMode
from picklebot.core.context import SharedContext
from picklebot.events.bus import EventBus
from picklebot.events.delivery import DeliveryWorker
from picklebot.events.types import Event, EventType
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.base import Job
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class InboundEventBridge:
    """Bridges INBOUND events to agent jobs."""

    def __init__(self, context: SharedContext, agent_id: str):
        self.context = context
        self.agent_id = agent_id

    async def handle_inbound(self, event: Event) -> None:
        """Handle INBOUND event by creating a Job."""
        if event.type != EventType.INBOUND:
            return

        # Create a job for this inbound event
        job = Job(
            session_id=event.session_id,
            agent_id=self.agent_id,
            message=event.content,
            mode=SessionMode.CHAT,
        )
        # Create a new future for this job
        job.result_future = asyncio.get_event_loop().create_future()

        # Put job in queue for AgentDispatcherWorker
        await self.context.agent_queue.put(job)
        logger.debug(f"Created job for INBOUND event, session={event.session_id}")

    def subscribe(self, eventbus: EventBus) -> None:
        """Subscribe to INBOUND events."""
        eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        logger.info("InboundEventBridge subscribed to INBOUND events")


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

        # Create INBOUND->Job bridge
        agent_id = config.default_agent
        self.inbound_bridge = InboundEventBridge(self.context, agent_id)

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

        # Subscribe InboundEventBridge to create Jobs from INBOUND events
        self.inbound_bridge.subscribe(self.context.eventbus)

        try:
            # Run workers concurrently
            # - MessageBusWorker: reads input, publishes INBOUND events
            # - AgentDispatcherWorker: processes Jobs, agent publishes OUTBOUND events
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
