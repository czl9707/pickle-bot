"""Console frontend implementation using Rich."""

import contextlib
from typing import Iterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.config import Config
from .base import Frontend


class ConsoleFrontend(Frontend):
    """Console-based frontend using Rich for formatting."""

    def __init__(self, config: Config):
        """
        Initialize console frontend.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.console = Console()

    def show_welcome(self) -> None:
        """Display welcome message panel."""
        self.console.print(
            Panel(
                Text(f"Welcome to {self.config.agent.name}!", style="bold cyan"),
                title="🐈 Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    def get_user_input(self) -> str:
        """Get user input."""
        return self.console.input("[bold green]You:[/bold green] ")

    def show_agent_response(self, content: str) -> None:
        """Display agent's final response to user."""
        self.console.print(f"[bold cyan]{self.config.agent.name}:[/bold cyan] {content}\n")

    def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        self.console.print(content)

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield
