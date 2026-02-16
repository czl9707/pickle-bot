"""Server CLI command for cron execution."""

import asyncio

import typer

from picklebot.core.context import SharedContext
from picklebot.core.cron_executor import CronExecutor


def server_command(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    config = ctx.obj.get("config")

    context = SharedContext(config)
    executor = CronExecutor(context)

    typer.echo("Starting pickle-bot server...")
    typer.echo(f"Crons path: {config.crons_path}")
    typer.echo("Press Ctrl+C to stop")

    try:
        asyncio.run(executor.run())
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")
