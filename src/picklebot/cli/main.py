"""CLI interface for pickle-bot using Typer."""

from pathlib import Path
from typing import Annotated

import questionary
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


# Global config option callback
def load_config_callback(ctx: typer.Context, workspace: str):
    """Load configuration and store it in the context."""
    workspace_path = Path(workspace)
    config_file = workspace_path / "config.user.yaml"

    try:
        if not config_file.exists():
            # Offer onboarding
            run_onboarding = questionary.confirm(
                "No configuration found. Run onboarding now?",
                default=True,
            ).ask()

            if run_onboarding:
                wizard = OnboardingWizard(workspace=workspace_path)
                wizard.run()
            else:
                console.print(
                    "[yellow]Run 'picklebot init' to set up configuration.[/yellow]"
                )
                raise typer.Exit(1)

        cfg = Config.load(workspace_path)
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg

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
    workspace = (
        ctx.obj.get("config").workspace if ctx.obj else Path.home() / ".pickle-bot"
    )
    wizard = OnboardingWizard(workspace=workspace)
    wizard.run()


if __name__ == "__main__":
    app()
