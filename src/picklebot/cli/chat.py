"""CLI command handlers for pickle-bot."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent import Agent
from picklebot.config import Config
from picklebot.tools.builtin_tools import register_builtin_tools
from picklebot.tools.registry import ToolRegistry


class Session:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        """
        Initialize the session.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.console = Console()

        # Set up tool registry
        registry = ToolRegistry()
        register_builtin_tools(registry)

        # Create agent with tool registry
        self.agent = Agent(config, tool_registry=registry)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        self._show_welcome()

        while True:
            try:
                user_input = self.console.input("[bold green]You:[/bold green] ")

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Get response from agent
                response = await self.agent.chat(user_input)

                self.console.print(f"[bold cyan]{self.config.agent.name}:[/bold cyan] {response}\n")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Session interrupted.[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def _show_welcome(self) -> None:
        """Display the welcome message panel."""
        self.console.print(
            Panel(
                Text(f"Welcome to {self.config.agent.name}!", style="bold cyan"),
                title="🐈‍⬛ Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")
