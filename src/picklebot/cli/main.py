"""CLI interface for pickle-bot using Typer."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from picklebot.cli.chat import ChatLoop
from picklebot.cli.server import server_command
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging

app = typer.Typer(
    name="picklebot",
    help="Pickle-Bot: Personal AI Assistant with pluggable tools",
    no_args_is_help=True,
    add_completion=True,
)

console = Console()


# Global config option callback
def load_config_callback(ctx: typer.Context, workspace: str):
    """Load configuration and store it in the context."""
    try:
        cfg = Config.load(Path(workspace))
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg

        # Set up logging without console output by default
        # Individual commands can enable console output if needed
        setup_logging(cfg, console_output=False)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)


@app.callback()
def main(
    ctx: typer.Context,
    workspace: str = typer.Option(
        Path.home() / ".pickle-bot",
        "--workspace",
        "-w",
        help="Path to workspace directory",
        callback=load_config_callback,
    ),
) -> None:
    """
    Pickle-Bot: Personal AI Assistant with pluggable tools.

    Configuration is loaded from ~/.pickle-bot/ by default.
    Use --workspace to specify a custom workspace directory.
    """
    # Config is loaded via callback, nothing to do here
    pass


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
    import asyncio

    config = ctx.obj.get("config")

    session = ChatLoop(config, agent_id=agent)
    asyncio.run(session.run())


@app.command("server")
def server(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    server_command(ctx)


if __name__ == "__main__":
    app()
