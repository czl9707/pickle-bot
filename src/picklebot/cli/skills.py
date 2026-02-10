"""Skills subcommand group for pickle-bot CLI."""

import typer
from rich.console import Console

from picklebot.core.config import Config
from picklebot.skills.builtin_skills import register_builtin_skills
from picklebot.skills.registry import SkillRegistry

skills_app = typer.Typer(
    help="Manage and interact with skills",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


@skills_app.command()
def list(
    ctx: typer.Context,
) -> None:
    """List all available skills."""
    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    skills = registry.list_all()

    console.print(
        typer.style(f"Available Skills: {len(skills)}", bold=True, fg="cyan")
    )

    for skill in skills:
        console.print(f"\n{typer.style(skill.name, bold=True, fg='cyan')}")
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
                console.print(
                    f"    - {param_name}: {param_info.get('description', 'N/A')}{required}"
                )


@skills_app.command()
def execute(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Name of the skill to execute"),
    args: str = typer.Option(
        None,
        "--args",
        "-a",
        help="Arguments as JSON string (e.g., '{\"text\": \"hello\"}')",
    ),
) -> None:
    """Execute a skill directly."""
    import asyncio
    import json

    # Parse args
    parsed_args = {}
    if args:
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in args: {e}[/red]")
            raise typer.Exit(1)

    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    # Execute skill
    async def _execute():
        try:
            result = await registry.execute_tool(name, **parsed_args)
            console.print(f"[cyan]Result:[/cyan] {result}")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error executing skill: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(_execute())


@skills_app.command()
def info(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Name of the skill"),
) -> None:
    """Show detailed information about a skill."""
    # Set up skill registry
    registry = SkillRegistry()
    register_builtin_skills(registry)

    skill = registry.get(name)
    if not skill:
        console.print(f"[red]Skill not found: {name}[/red]")
        console.print("\nAvailable skills:")
        for s in registry.list_all():
            console.print(f"  - {s.name}")
        raise typer.Exit(1)

    console.print(typer.style(f"Skill: {skill.name}", bold=True, fg="cyan"))
    console.print(f"Description: {skill.description}")
    console.print(f"\nParameters:")

    if skill.parameters.get("properties"):
        for param_name, param_info in skill.parameters["properties"].items():
            required = (
                typer.style(" required", fg="red", bold=True)
                if param_name in skill.parameters.get("required", [])
                else typer.style(" optional", fg="green")
            )
            param_type = param_info.get("type", "unknown")
            console.print(f"  [bold]{param_name}[/bold] ({param_type}){required}")
            console.print(
                f"    {param_info.get('description', 'No description')}"
            )
    else:
        console.print("  No parameters")
