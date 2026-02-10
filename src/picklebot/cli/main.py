"""CLI interface for pickle-bot using Typer."""

from pathlib import Path

import typer
from rich.console import Console

from picklebot.cli.chat import run_interactive_session
from picklebot.config import Config
from picklebot.utils.logging import setup_logging

app = typer.Typer(
    name="picklebot",
    help="Pickle-Bot: Personal AI Assistant with pluggable tools",
    no_args_is_help=True,
    add_completion=True,
)

console = Console()

# Global config option callback
def load_config_callback(ctx: typer.Context, config: str):
    """Load configuration and store it in the context."""
    try:
        cfg = Config.load(Path(config))
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg

        setup_logging(level=cfg.logging.level)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option(
        Path.home() / ".pickle-bot",
        "--config",
        "-c",
        help="Path to configuration directory",
        callback=load_config_callback,
    ),
) -> None:
    """
    Pickle-Bot: Personal AI Assistant with pluggable tools.

    Configuration is loaded from ~/.pickle-bot/ by default.
    Use --config to specify a custom configuration directory.
    """
    # Config is loaded via callback, nothing to do here
    pass


@app.command()
def chat(
    ctx: typer.Context,
) -> None:
    """Start interactive chat session."""
    import asyncio

    config = ctx.obj.get("config")

    asyncio.run(run_interactive_session(config))


if __name__ == "__main__":
    app()
