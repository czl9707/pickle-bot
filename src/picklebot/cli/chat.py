"""Chat CLI command for interactive sessions."""

import asyncio
import logging
import warnings

# Suppress all warnings at module level (e.g., RequestsDependencyWarning)
warnings.filterwarnings("ignore")

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Prompt  # noqa: E402
from rich.text import Text  # noqa: E402

from picklebot.core.events import OutboundEvent, CliEventSource  # noqa: E402
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

        # Subscribe to outbound events
        self.context.eventbus.subscribe(OutboundEvent, self.handle_outbound_event)

    async def handle_outbound_event(self, event: OutboundEvent) -> None:
        """Handle outbound events by adding to response queue."""
        await self.response_queue.put(event)
        self.context.eventbus.ack(event)

    def get_user_input(self) -> str:
        """Get user input with styled prompt.

        Returns:
            Trimmed user input, or empty string if quit command
        """
        # Create cyan prompt
        prompt_text = Text("You: ", style="cyan")

        # Get input (Prompt.get_input handles the styling)
        user_input = Prompt.ask(prompt_text, console=self.console)

        # Trim whitespace
        user_input = user_input.strip()

        return user_input

    def display_agent_response(self, content: str) -> None:
        """Display agent response with styled prefix.

        Args:
            content: Agent response content
        """
        # Create green prefix
        prefix = Text("Agent: ", style="green")

        # Print prefix and content
        self.console.print(prefix, end="")
        self.console.print(content)

        # Add separator line
        self.console.print()

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

        # Start workers
        for worker in self.workers:
            worker.start()

        try:
            while True:
                # Get user input
                user_input = await asyncio.to_thread(self.get_user_input)

                # Check for quit commands
                if user_input.lower() in ("quit", "exit", "q"):
                    self.console.print("\nGoodbye!")
                    break

                # Skip empty input
                if not user_input:
                    continue

                # Publish InboundEvent
                from picklebot.core.events import InboundEvent
                import time

                # Get or create session (simplified for CLI)
                session_id = "cli-session"

                event = InboundEvent(
                    session_id=session_id,
                    agent_id="default",
                    source=CliEventSource(),
                    content=user_input,
                    timestamp=time.time(),
                )
                await self.context.eventbus.publish(event)

                # Wait for agent response
                try:
                    response = await asyncio.wait_for(
                        self.response_queue.get(), timeout=30.0
                    )
                    # Display response
                    self.display_agent_response(response.content)
                except asyncio.TimeoutError:
                    self.console.print("[red]Agent response timed out[/red]")
                    self.console.print()

        except (KeyboardInterrupt, EOFError):
            self.console.print("\nGoodbye!")
        finally:
            # Stop all workers gracefully
            for worker in self.workers:
                await worker.stop()


def chat_command(ctx: typer.Context) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config)
    asyncio.run(chat_loop.run())
