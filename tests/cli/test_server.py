"""Tests for server CLI command."""

from unittest.mock import patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.server.server import Server
from picklebot.utils.config import MessageBusConfig, TelegramConfig


class TestServer:
    """Test Server class setup."""

    @pytest.mark.anyio
    async def test_server_initializes_with_context(self, test_config):
        """Server initializes successfully with context."""
        context = SharedContext(test_config)
        server = Server(context)

        assert server.context == context
        assert server.agent_queue is not None
        assert server.workers == []

    @pytest.mark.anyio
    async def test_server_setup_workers_when_messagebus_disabled(self, test_config):
        """Server sets up AgentDispatcherWorker and CronWorker when messagebus disabled."""
        context = SharedContext(test_config)
        server = Server(context)
        server._setup_workers()

        # Should have 2 workers: AgentDispatcherWorker and CronWorker
        assert len(server.workers) == 2
        worker_types = [w.__class__.__name__ for w in server.workers]
        assert "AgentDispatcherWorker" in worker_types
        assert "CronWorker" in worker_types
        assert "MessageBusWorker" not in worker_types

    @pytest.mark.anyio
    async def test_server_setup_workers_when_messagebus_enabled(self, test_config):
        """Server sets up MessageBusWorker when messagebus enabled."""
        test_config.messagebus = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=True, bot_token="test"),
        )

        # Mock MessageBusWorker to avoid needing real agent
        with patch("picklebot.server.server.MessageBusWorker") as mock_worker_class:
            context = SharedContext(test_config)
            server = Server(context)
            server._setup_workers()

            # Should have 3 workers: AgentDispatcherWorker, CronWorker, and MessageBusWorker
            assert len(server.workers) == 3
            worker_types = [w.__class__.__name__ for w in server.workers]
            assert "AgentDispatcherWorker" in worker_types
            assert "CronWorker" in worker_types
            assert mock_worker_class.called  # MessageBusWorker was created

    @pytest.mark.anyio
    async def test_server_does_not_setup_messagebus_worker_when_no_buses(
        self, test_config
    ):
        """Server doesn't setup MessageBusWorker if no buses configured."""
        test_config.messagebus = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=False, bot_token="test"),
        )

        context = SharedContext(test_config)
        server = Server(context)
        server._setup_workers()

        # Should have only 2 workers: AgentDispatcherWorker and CronWorker
        assert len(server.workers) == 2
        worker_types = [w.__class__.__name__ for w in server.workers]
        assert "AgentDispatcherWorker" in worker_types
        assert "CronWorker" in worker_types
        assert "MessageBusWorker" not in worker_types
