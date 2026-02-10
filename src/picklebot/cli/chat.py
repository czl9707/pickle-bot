"""CLI command handlers for pickle-bot."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent import Agent
from picklebot.config import Config
from picklebot.skills.builtin_skills import register_builtin_skills
from picklebot.skills.registry import SkillRegistry

console = Console()


async def run_interactive_session(config: Config) -> None:
    """Run interactive chat session."""
    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    # Create agent
    agent = Agent(config)
    agent.set_skill_registry(registry)

    # Welcome message
    console.print(
        Panel(
            Text(f"Welcome to {config.agent.name}!", style="bold cyan"),
            title="🐈‍⬛ Pickle",
            border_style="cyan",
        )
    )
    console.print("Type 'quit' or 'exit' to end the session.\n")

    # Chat loop
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ")

            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("[yellow]Goodbye![/yellow]")
                break

            if not user_input.strip():
                continue

            # Get response from agent
            response = await agent.chat(user_input)

            console.print(f"[bold cyan]{config.agent.name}:[/bold cyan] {response}\n")

        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted.[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

