"""CLI command handlers for pickle-bot."""

import asyncio
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent import Agent
from picklebot.core.config import AgentConfig
from picklebot.skills.builtin_skills import register_builtin_skills
from picklebot.skills.registry import SkillRegistry

console = Console()


async def run_chat(config_path: Optional[str] = None) -> None:
    """Run interactive chat session."""
    # Load configuration
    config = AgentConfig.load(config_path)

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
            title="🤖 Pickle-Bot",
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


def list_skills(config_path: Optional[str] = None) -> None:
    """List all available skills."""
    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    skills = registry.list_all()

    console.print(Panel(f"Available Skills: {len(skills)}", border_style="cyan"))

    for skill in skills:
        console.print(f"\n[bold cyan]{skill.name}[/bold cyan]")
        console.print(f"  {skill.description}")

        # Show parameters if any
        if skill.parameters.get("properties"):
            console.print("  Parameters:")
            for param_name, param_info in skill.parameters["properties"].items():
                required = (
                    ", required"
                    if param_name in skill.parameters.get("required", [])
                    else ""
                )
                console.print(f"    - {param_name}: {param_info.get('description', 'N/A')}{required}")


async def execute_skill_async(
    skill_name: str, args: dict, config_path: Optional[str] = None
) -> None:
    """Execute a skill directly."""
    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    try:
        result = await registry.execute_tool(skill_name, **args)
        console.print(f"[cyan]Result:[/cyan] {result}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error executing skill: {e}[/red]")


def execute_skill(skill_name: str, args: dict, config_path: Optional[str] = None) -> None:
    """Execute a skill directly (sync wrapper)."""
    asyncio.run(execute_skill_async(skill_name, args, config_path))


def show_status(config_path: Optional[str] = None) -> None:
    """Show agent status."""
    try:
        config = AgentConfig.load(config_path)
        console.print(Panel("Agent Status", border_style="cyan"))
        console.print(f"Name: {config.agent.name}")
        console.print(f"LLM Provider: {config.llm.provider}")
        console.print(f"Model: {config.llm.model}")
        console.print(f"API Base: {config.llm.api_base}")
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
