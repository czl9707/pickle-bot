"""Server CLI command for cron execution."""

import asyncio
import logging

import typer

from picklebot.core.context import SharedContext
from picklebot.core.cron_executor import CronExecutor
from picklebot.core.messagebus_executor import MessageBusExecutor
from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import MessageBusConfig
from picklebot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def create_buses_from_config(messagebus_config: MessageBusConfig) -> list[MessageBus]:
    """
    Create message bus instances based on configuration.

    Args:
        messagebus_config: Message bus configuration

    Returns:
        List of configured message bus instances
    """
    buses = []

    # Only create buses if telegram config exists and is enabled
    if messagebus_config.telegram and messagebus_config.telegram.enabled:
        buses.append(TelegramBus(messagebus_config.telegram))

    # Only create buses if discord config exists and is enabled
    if messagebus_config.discord and messagebus_config.discord.enabled:
        buses.append(DiscordBus(messagebus_config.discord))

    return buses


async def _run_server(
    context: SharedContext, messagebus_config: MessageBusConfig
) -> None:
    """
    Run both CronExecutor and MessageBusExecutor.

    Args:
        context: Shared application context
        messagebus_config: Message bus configuration
    """
    # Start CronExecutor
    cron_task = asyncio.create_task(CronExecutor(context).run())

    # Start MessageBusExecutor if enabled and buses are configured
    if messagebus_config.enabled:
        buses = create_buses_from_config(messagebus_config)
        if buses:
            logger.info(f"Starting MessageBusExecutor with {len(buses)} bus(es)")
            bus_task = asyncio.create_task(MessageBusExecutor(context, buses).run())
            await asyncio.gather(cron_task, bus_task)
        else:
            logger.warning("MessageBus enabled but no buses configured")
            await cron_task
    else:
        await cron_task


def server_command(
    ctx: typer.Context,
) -> None:
    """Start the 24/7 server for cron job execution."""
    config = ctx.obj.get("config")

    # Enable console logging for server mode
    setup_logging(config, console_output=True)

    typer.echo("Starting pickle-bot server...")
    typer.echo(f"Crons path: {config.crons_path}")

    # Show message bus status
    if config.messagebus.enabled:
        enabled_buses = []
        if config.messagebus.telegram and config.messagebus.telegram.enabled:
            enabled_buses.append("telegram")
        if config.messagebus.discord and config.messagebus.discord.enabled:
            enabled_buses.append("discord")
        typer.echo(f"Message bus enabled with platform(s): {', '.join(enabled_buses)}")
    else:
        typer.echo("Message bus disabled")

    typer.echo("Press Ctrl+C to stop")

    try:
        context = SharedContext(config)
        asyncio.run(_run_server(context, config.messagebus))
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")
