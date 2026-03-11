"""Chat CLI command for interactive sessions."""

import asyncio
import logging
import warnings

from picklebot.core.agent import Agent

# Suppress all warnings at module level (e.g., RequestsDependencyWarning)
warnings.filterwarnings("ignore")

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Prompt  # noqa: E402
from rich.text import Text  # noqa: E402

from picklebot.core.events import (  # noqa: E402
    OutboundEvent,
    CliEventSource,
    InboundEvent,
)
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

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.console = Console()
        self.context = SharedContext(config=config, channels=[])

        self.workers: list[Worker] = [
            self.context.eventbus,
            AgentWorker(self.context),
        ]

        self.response_queue: asyncio.Queue[OutboundEvent] = asyncio.Queue()
        self.context.eventbus.subscribe(OutboundEvent, self.handle_outbound_event)

        if not agent_id:
            agent_id = self.context.routing_table.resolve(str(CliEventSource()))
        if not agent_id:
            agent_id = self.config.default_agent
        self.agent = self.context.agent_loader.load(agent_id)

    async def handle_outbound_event(self, event: OutboundEvent) -> None:
        """Handle outbound events by adding to response queue."""
        await self.response_queue.put(event)
        self.context.eventbus.ack(event)

    def get_user_input(self) -> str:
        """Get user input with styled prompt.

        Returns:
            Trimmed user input, or empty string if quit command
        """
        prompt_text = Text("You", style="cyan")
        user_input = Prompt.ask(prompt_text, console=self.console)
        return user_input.strip()

    def display_agent_response(self, content: str) -> None:
        """Display agent response with styled prefix.

        Args:
            content: Agent response content
        """
        prefix = Text(f"{self.agent.id}: ", style="green")

        self.console.print(prefix, end="")
        self.console.print(content)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        self.console.print(
            Panel(
                Text("Welcome to pickle-bot!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

        for worker in self.workers:
            worker.start()

        session_id = (
            Agent(self.agent, self.context).new_session(CliEventSource()).session_id
        )

        try:
            while True:
                user_input = await asyncio.to_thread(self.get_user_input)
                if user_input.lower() in ("quit", "exit", "q"):
                    self.console.print("\nGoodbye!")
                    break

                if not user_input:
                    continue

                event = InboundEvent(
                    session_id=session_id,
                    source=CliEventSource(),
                    content=user_input,
                )
                await self.context.eventbus.publish(event)

                try:
                    response = await asyncio.wait_for(
                        self.response_queue.get(), timeout=60.0
                    )

                    self.display_agent_response(response.content)
                except asyncio.TimeoutError:
                    self.console.print("[red]Agent response timed out[/red]")
                    self.console.print()

        except (KeyboardInterrupt, EOFError):
            self.console.print("\nGoodbye!")
        finally:
            for worker in self.workers:
                await worker.stop()


def chat_command(ctx: typer.Context, agent_id: str | None = None) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config, agent_id=agent_id)
    asyncio.run(chat_loop.run())
