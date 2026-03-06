"""Tests for SharedContext."""

from unittest.mock import patch, MagicMock

import pytest

from picklebot.core.context import SharedContext
from picklebot.core.eventbus import EventBus
from picklebot.core.events import InboundEvent, OutboundEvent, AgentEventSource
from picklebot.channel.telegram_channel import TelegramEventSource, TelegramChannel
from picklebot.core.routing import RoutingTable
from picklebot.utils.config import Config, LLMConfig, TelegramConfig


# Fixtures for tests that create their own config
@pytest.fixture
def mock_config(tmp_path):
    """Config without any channels enabled."""
    return Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        default_agent="test",
    )


@pytest.fixture
def config_from_file(tmp_path):
    """Config loaded from a YAML file."""
    config_file = tmp_path / "config.user.yaml"
    config_file.write_text(
        """default_agent: test-agent
llm:
  provider: openai
  model: gpt-4
  api_key: test
"""
    )
    return Config.load(tmp_path)


class TestSharedContextBasics:
    """Tests for basic SharedContext initialization."""

    def test_context_initialization(self, test_context):
        """SharedContext should initialize with all required components."""
        assert test_context.config is not None
        assert test_context.history_store is not None
        assert test_context.agent_loader is not None
        assert test_context.skill_loader is not None
        assert test_context.cron_loader is not None
        assert test_context.command_registry is not None
        assert test_context.eventbus is not None

    def test_shared_context_has_routing_table(self, test_context):
        """SharedContext should initialize RoutingTable."""
        assert hasattr(test_context, "routing_table")
        assert isinstance(test_context.routing_table, RoutingTable)


class TestSharedContextEventBus:
    """Tests for EventBus integration with SharedContext."""

    def test_shared_context_has_eventbus(self, config_from_file):
        """SharedContext should have an EventBus instance initialized."""
        context = SharedContext(config_from_file)
        assert hasattr(context, "eventbus")
        assert isinstance(context.eventbus, EventBus)

    @pytest.mark.asyncio
    async def test_subscribe_by_event_class(self, config_from_file):
        """EventBus.subscribe should accept event classes with type-safe handlers."""
        context = SharedContext(config_from_file)
        eventbus = context.eventbus

        received_inbound = []
        received_outbound = []

        async def inbound_handler(event: InboundEvent):
            received_inbound.append(event)

        async def outbound_handler(event: OutboundEvent):
            received_outbound.append(event)

        # Subscribe by event class
        eventbus.subscribe(InboundEvent, inbound_handler)
        eventbus.subscribe(OutboundEvent, outbound_handler)

        # Create test events
        inbound = InboundEvent(
            session_id="test",
            agent_id="test",
            content="inbound",
            source=TelegramEventSource(user_id="user1", chat_id="chat1"),
        )
        outbound = OutboundEvent(
            session_id="test",
            agent_id="test",
            content="outbound",
            source=AgentEventSource(agent_id="test"),
        )

        # Notify subscribers
        await eventbus._notify_subscribers(inbound)
        await eventbus._notify_subscribers(outbound)

        # Verify correct handlers called
        assert len(received_inbound) == 1
        assert received_inbound[0].content == "inbound"
        assert len(received_outbound) == 1
        assert received_outbound[0].content == "outbound"


class TestSharedContextCustomChannels:
    """Tests for optional channels parameter in SharedContext.__init__."""

    def test_backward_compatible_loads_from_config_when_channels_none(
        self, mock_config
    ):
        """When channels=None (default), should load from config like before."""
        with patch("picklebot.core.context.Channel.from_config") as mock_from_config:
            mock_from_config.return_value = []

            context = SharedContext(config=mock_config, channels=None)

            # Should have called from_config with the config
            mock_from_config.assert_called_once_with(mock_config)
            assert context.channels == []

    def test_backward_compatible_default_behavior(self, mock_config):
        """Without channels parameter, should load from config (backward compat)."""
        with patch("picklebot.core.context.Channel.from_config") as mock_from_config:
            mock_from_config.return_value = []

            # Call without channels parameter - should work like before
            context = SharedContext(config=mock_config)

            mock_from_config.assert_called_once_with(mock_config)
            assert context.channels == []

    def test_empty_channels_list_is_used_not_config(self, mock_config):
        """Empty list should be used, not fall back to config."""
        with patch("picklebot.core.context.Channel.from_config") as mock_from_config:
            mock_from_config.return_value = [
                MagicMock()
            ]  # Would return something if called

            # Pass empty list - should NOT call from_config
            context = SharedContext(config=mock_config, channels=[])

            mock_from_config.assert_not_called()
            assert context.channels == []

    def test_multiple_channels_accepted(self, mock_config):
        """Multiple channels can be passed."""
        channel1 = TelegramChannel(config=TelegramConfig(bot_token="test-token-1"))
        channel2 = TelegramChannel(config=TelegramConfig(bot_token="test-token-2"))

        context = SharedContext(config=mock_config, channels=[channel1, channel2])

        assert len(context.channels) == 2
        assert context.channels[0] is channel1
        assert context.channels[1] is channel2
