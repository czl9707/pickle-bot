"""Tests for server CLI command."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.cli.server import create_buses_from_config, _run_server
from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import (
    TelegramConfig,
    DiscordConfig,
    MessageBusConfig,
    Config,
    LLMConfig,
)


class TestCreateBusesFromConfig:
    """Test create_buses_from_config helper function."""

    def test_creates_empty_list_when_no_buses_enabled(self):
        """Return empty list when no message buses are enabled."""
        config = Config(
            workspace=Path("/tmp/test"),
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(enabled=False),
        )
        result = create_buses_from_config(config.messagebus)
        assert result == []

    def test_creates_empty_list_when_only_telegram_disabled(self):
        """Return empty list when telegram is disabled."""
        telegram_config = TelegramConfig(enabled=False, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",  # Required when enabled
            telegram=telegram_config,
        )
        result = create_buses_from_config(messagebus_config)
        assert result == []

    def test_creates_empty_list_when_only_discord_disabled(self):
        """Return empty list when discord is disabled."""
        discord_config = DiscordConfig(enabled=False, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="discord",  # Required when enabled
            discord=discord_config,
        )
        result = create_buses_from_config(messagebus_config)
        assert result == []

    def test_creates_single_telegram_bus(self):
        """Create TelegramBus when only telegram is enabled."""
        telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
        )
        result = create_buses_from_config(messagebus_config)

        assert len(result) == 1
        assert isinstance(result[0], TelegramBus)
        assert result[0].config == telegram_config

    def test_creates_single_discord_bus(self):
        """Create DiscordBus when only discord is enabled."""
        discord_config = DiscordConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="discord",
            discord=discord_config,
        )
        result = create_buses_from_config(messagebus_config)

        assert len(result) == 1
        assert isinstance(result[0], DiscordBus)
        assert result[0].config == discord_config

    def test_creates_multiple_buses(self):
        """Create both buses when both are enabled."""
        telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
        discord_config = DiscordConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
            discord=discord_config,
        )
        result = create_buses_from_config(messagebus_config)

        assert len(result) == 2
        assert isinstance(result[0], TelegramBus)
        assert isinstance(result[1], DiscordBus)


class TestRunServer:
    """Test _run_server async function."""

    @pytest.mark.asyncio
    async def test_starts_cron_executor_when_messagebus_disabled(self):
        """Start CronExecutor when messagebus is disabled."""
        config = Config(
            workspace=Path("/tmp/test"),
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(enabled=False),
        )

        with (
            patch("picklebot.cli.server.SharedContext") as mock_context_class,
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.create_buses_from_config") as mock_create_buses,
        ):
            mock_context = MagicMock()
            mock_context_class.return_value = mock_context

            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron

            await _run_server(mock_context, config.messagebus)

            mock_cron_executor.assert_called_once_with(mock_context)
            mock_create_buses.assert_not_called()

    @pytest.mark.asyncio
    async def test_starts_messagebus_executor_when_enabled(self):
        """Start MessageBusExecutor when messagebus is enabled."""
        config = Config(
            workspace=Path("/tmp/test"),
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(
                enabled=True,
                default_platform="telegram",
                telegram=TelegramConfig(enabled=True, bot_token="test"),
            ),
        )

        with (
            patch("picklebot.cli.server.SharedContext") as mock_context_class,
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
            patch("picklebot.cli.server.create_buses_from_config") as mock_create_buses,
        ):
            mock_context = MagicMock()
            mock_context_class.return_value = mock_context

            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron

            mock_bus = AsyncMock()
            mock_bus_executor.return_value = mock_bus

            mock_create_buses.return_value = [MagicMock(spec=MessageBus)]

            await _run_server(mock_context, config.messagebus)

            mock_cron_executor.assert_called_once_with(mock_context)
            mock_bus_executor.assert_called_once_with(
                mock_context, mock_create_buses.return_value
            )

    @pytest.mark.asyncio
    async def test_does_not_start_messagebus_when_no_buses(self):
        """Don't start MessageBusExecutor if create_buses_from_config returns empty list."""
        config = Config(
            workspace=Path("/tmp/test"),
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(
                enabled=True,
                default_platform="telegram",
                telegram=TelegramConfig(enabled=False, bot_token="test"),
            ),
        )

        with (
            patch("picklebot.cli.server.SharedContext") as mock_context_class,
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
            patch("picklebot.cli.server.create_buses_from_config") as mock_create_buses,
        ):
            mock_context = MagicMock()
            mock_context_class.return_value = mock_context

            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron

            mock_create_buses.return_value = []

            await _run_server(mock_context, config.messagebus)

            mock_cron_executor.assert_called_once_with(mock_context)
            mock_bus_executor.assert_not_called()
