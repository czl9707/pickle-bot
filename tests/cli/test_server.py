"""Tests for server CLI command."""

from unittest.mock import patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.server.server import Server
from picklebot.utils.config import ChannelConfig, TelegramConfig


class TestServer:
    """Test Server class setup."""

    async def test_server_initializes_with_context(self, test_config):
        """Server initializes successfully with context."""
        context = SharedContext(test_config)
        server = Server(context)

        assert server.context == context
        assert server.workers == []

    async def test_server_setup_workers_when_channel_disabled(self, test_config):
        """Server sets up core workers when channel disabled."""
        context = SharedContext(test_config)
        server = Server(context)
        server._setup_workers()

        # Should have 5 core workers: EventBus, AgentWorker, CronWorker, DeliveryWorker, WebSocketWorker
        assert len(server.workers) == 5
        worker_types = [w.__class__.__name__ for w in server.workers]
        assert "EventBus" in worker_types
        assert "AgentWorker" in worker_types
        assert "DeliveryWorker" in worker_types
        assert "CronWorker" in worker_types
        assert "WebSocketWorker" in worker_types
        assert "ChannelWorker" not in worker_types

    async def test_server_setup_workers_when_channel_enabled(self, test_config):
        """Server sets up ChannelWorker when channel enabled."""
        test_config.channels = ChannelConfig(
            enabled=True,
            telegram=TelegramConfig(enabled=True, bot_token="test"),
        )

        # Mock ChannelWorker to avoid needing real agent
        with patch("picklebot.server.server.ChannelWorker") as mock_worker_class:
            context = SharedContext(test_config)
            server = Server(context)
            server._setup_workers()

            # Should have 6 workers: 5 core + ChannelWorker
            assert len(server.workers) == 6
            worker_types = [w.__class__.__name__ for w in server.workers]
            assert "EventBus" in worker_types
            assert "AgentWorker" in worker_types
            assert "DeliveryWorker" in worker_types
            assert "CronWorker" in worker_types
            assert "WebSocketWorker" in worker_types
            assert mock_worker_class.called  # ChannelWorker was created

    async def test_server_does_not_setup_channel_worker_when_no_channels(
        self, test_config
    ):
        """Server doesn't setup ChannelWorker if no channels configured."""
        test_config.channels = ChannelConfig(
            enabled=True,
            telegram=TelegramConfig(enabled=False, bot_token="test"),
        )

        context = SharedContext(test_config)
        server = Server(context)
        server._setup_workers()

        # Should have 5 core workers (no ChannelWorker)
        assert len(server.workers) == 5
        worker_types = [w.__class__.__name__ for w in server.workers]
        assert "EventBus" in worker_types
        assert "AgentWorker" in worker_types
        assert "DeliveryWorker" in worker_types
        assert "CronWorker" in worker_types
        assert "WebSocketWorker" in worker_types
        assert "ChannelWorker" not in worker_types
