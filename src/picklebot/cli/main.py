"""CLI interface for pickle-bot using Typer."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from picklebot.cli.chat import chat_command
from picklebot.cli.onboarding import OnboardingWizard
from picklebot.cli.server import server_command
from picklebot.utils.config import Config

app = typer.Typer(
    name="picklebot",
    help="Pickle-Bot: Personal AI Assistant with pluggable tools",
    no_args_is_help=True,
    add_completion=True,
)

console = Console()


# Global workspace option callback
def workspace_callback(ctx: typer.Context, workspace: str):
    """Store workspace path in context for later use."""
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = Path(workspace)
    return Path(workspace)


@app.callback()
def main(
    ctx: typer.Context,
    workspace: str = typer.Option(
        Path.home() / ".pickle-bot",
        "--workspace",
        "-w",
        help="Path to workspace directory",
        callback=workspace_callback,
    ),
) -> None:
    """
    Pickle-Bot: Personal AI Assistant with pluggable tools.

    Configuration is loaded from ~/.pickle-bot/ by default.
    Use --workspace to specify a custom workspace directory.
    """
    # Skip config check for init command - it handles its own setup
    if ctx.invoked_subcommand == "init":
        return

    workspace_path = ctx.obj["workspace"]
    config_file = workspace_path / "config.user.yaml"

    if not config_file.exists():
        console.print("[yellow]No configuration found.[/yellow]")
        console.print("Run [bold]picklebot init[/bold] to set up.")
        raise typer.Exit(1)

    try:
        cfg = Config.load(workspace_path)
        ctx.obj["config"] = cfg
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def chat(
    ctx: typer.Context,
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            "-a",
            help="Agent ID to use (overrides default_agent from config)",
        ),
    ] = None,
) -> None:
    """Start interactive chat session."""
    chat_command(ctx, agent_id=agent)


@app.command("server")
def server(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    server_command(ctx)


@app.command()
def init(
    ctx: typer.Context,
) -> None:
    """Initialize pickle-bot configuration with interactive onboarding."""
    workspace = ctx.obj.get("workspace", Path.home() / ".pickle-bot")
    wizard = OnboardingWizard(workspace=workspace)
    wizard.run()


if __name__ == "__main__":
    app()
