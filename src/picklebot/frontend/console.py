"""Console frontend implementation using Rich."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .base import Frontend


class ConsoleFrontend(Frontend):
    """Console-based frontend using Rich for formatting."""

    def __init__(self):
        self.console = Console()

    async def show_welcome(self) -> None:
        """Display welcome message panel."""
        self.console.print(
            Panel(
                Text("Welcome to pickle-bot!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    async def show_message(self, content: str, agent_id: str | None = None) -> None:
        """Display a message with optional agent context."""
        if agent_id:
            self.console.print(f"[bold cyan]{agent_id}:[/bold cyan] {content}")
        else:
            self.console.print(content)

    async def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        self.console.print(content)

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Display subagent dispatch start."""
        self.console.print(f"[dim]{calling_agent} -> @{target_agent}: {task}[/dim]")
        yield
