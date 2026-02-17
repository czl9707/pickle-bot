"""Tests for server CLI command."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.cli.server import _run_server
from picklebot.core.context import SharedContext
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import (
    TelegramConfig,
    DiscordConfig,
    MessageBusConfig,
    Config,
    LLMConfig,
)


class TestSharedContextMessageBus:
    """Test SharedContext.messagebus_buses property."""

    def test_creates_empty_list_when_no_buses_enabled(self, tmp_path):
        """Return empty list when no message buses are enabled."""
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(enabled=False),
        )
        context = SharedContext(config)
        result = context.messagebus_buses
        assert result == []

    def test_creates_empty_list_when_only_telegram_disabled(self, tmp_path):
        """Return empty list when telegram is disabled."""
        telegram_config = TelegramConfig(enabled=False, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
        )
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=messagebus_config,
        )
        context = SharedContext(config)
        result = context.messagebus_buses
        assert result == []

    def test_creates_empty_list_when_only_discord_disabled(self, tmp_path):
        """Return empty list when discord is disabled."""
        discord_config = DiscordConfig(enabled=False, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="discord",
            discord=discord_config,
        )
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=messagebus_config,
        )
        context = SharedContext(config)
        result = context.messagebus_buses
        assert result == []

    def test_creates_single_telegram_bus(self, tmp_path):
        """Create TelegramBus when only telegram is enabled."""
        telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
        )
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=messagebus_config,
        )
        context = SharedContext(config)
        result = context.messagebus_buses

        assert len(result) == 1
        assert isinstance(result[0], TelegramBus)
        assert result[0].config == telegram_config

    def test_creates_single_discord_bus(self, tmp_path):
        """Create DiscordBus when only discord is enabled."""
        discord_config = DiscordConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="discord",
            discord=discord_config,
        )
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=messagebus_config,
        )
        context = SharedContext(config)
        result = context.messagebus_buses

        assert len(result) == 1
        assert isinstance(result[0], DiscordBus)
        assert result[0].config == discord_config

    def test_creates_multiple_buses(self, tmp_path):
        """Create both buses when both are enabled."""
        telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
        discord_config = DiscordConfig(enabled=True, bot_token="test_token")
        messagebus_config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
            discord=discord_config,
        )
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=messagebus_config,
        )
        context = SharedContext(config)
        result = context.messagebus_buses

        assert len(result) == 2
        assert isinstance(result[0], TelegramBus)
        assert isinstance(result[1], DiscordBus)

    def test_lazy_initialization(self, tmp_path):
        """Buses are only created once and cached."""
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(enabled=False),
        )
        context = SharedContext(config)

        # Access twice
        result1 = context.messagebus_buses
        result2 = context.messagebus_buses

        # Should be the same object (cached)
        assert result1 is result2


class TestRunServer:
    """Test _run_server async function."""

    @pytest.mark.asyncio
    async def test_starts_cron_executor_when_messagebus_disabled(self, tmp_path):
        """Start CronExecutor when messagebus is disabled."""
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(enabled=False),
        )

        with patch("picklebot.cli.server.CronExecutor") as mock_cron_executor:
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            context = SharedContext(config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_starts_messagebus_executor_when_enabled(self, tmp_path):
        """Start MessageBusExecutor when messagebus is enabled."""
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(
                enabled=True,
                default_platform="telegram",
                telegram=TelegramConfig(enabled=True, bot_token="test"),
            ),
        )

        with (
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
        ):
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            mock_bus = AsyncMock()
            mock_bus_executor.return_value = mock_bus
            mock_bus.run = AsyncMock()

            context = SharedContext(config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)
            mock_bus_executor.assert_called_once_with(context, context.messagebus_buses)

    @pytest.mark.asyncio
    async def test_does_not_start_messagebus_when_no_buses(self, tmp_path):
        """Don't start MessageBusExecutor if no buses are configured."""
        config = Config(
            workspace=tmp_path,
            llm=LLMConfig(provider="test", model="test", api_key="test"),
            default_agent="test",
            messagebus=MessageBusConfig(
                enabled=True,
                default_platform="telegram",
                telegram=TelegramConfig(enabled=False, bot_token="test"),
            ),
        )

        with (
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
        ):
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            context = SharedContext(config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)
            mock_bus_executor.assert_not_called()
