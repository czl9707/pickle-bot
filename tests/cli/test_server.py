"""Tests for server CLI command."""

from unittest.mock import AsyncMock, patch

import pytest

from picklebot.cli.server import _run_server
from picklebot.core.context import SharedContext
from picklebot.utils.config import (
    TelegramConfig,
    MessageBusConfig,
    Config,
    LLMConfig,
)

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
