"""CLI interface for pickle-bot using Typer."""

import asyncio
from typing import Optional

import typer

from picklebot.cli.commands import (
    execute_skill,
    list_skills,
    run_chat,
    show_status,
)
from picklebot.utils.logging import setup_logging

app = typer.Typer(
    name="picklebot",
    help="Pickle-Bot: Personal AI Assistant with pluggable skills",
    no_args_is_help=True,
)


@app.command()
def chat(
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Start interactive chat session."""
    setup_logging(level="DEBUG" if verbose else "INFO")
    asyncio.run(run_chat(config))


@app.command("skill")
def skill_commands(
    action: str = typer.Argument(..., help="Action: list, execute, info"),
    name: str = typer.Argument(None, help="Skill name (for execute/info)"),
) -> None:
    """Manage and interact with skills."""
    if action == "list":
        list_skills()
    elif action == "execute":
        if not name:
            typer.echo("Error: skill name required for execute", err=True)
            raise typer.Exit(1)
        execute_skill(name, {})
    elif action == "info":
        if not name:
            typer.echo("Error: skill name required for info", err=True)
            raise typer.Exit(1)
        # For now, just list skills (info could show more detail later)
        list_skills()
    else:
        typer.echo(f"Unknown action: {action}", err=True)
        typer.echo("Available actions: list, execute, info")
        raise typer.Exit(1)


@app.command()
def status(
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Show agent status."""
    show_status(config)


if __name__ == "__main__":
    app()
