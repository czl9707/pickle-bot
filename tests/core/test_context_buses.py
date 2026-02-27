"""Tests for SharedContext custom buses parameter."""

from unittest.mock import patch, MagicMock

import pytest

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def mock_config(tmp_path):
    """Config without any messagebus enabled."""
    return Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        default_agent="test",
    )


class TestSharedContextCustomBuses:
    """Tests for optional buses parameter in SharedContext.__init__."""

    def test_accepts_buses_parameter(self, mock_config):
        """SharedContext should accept optional buses parameter."""
        cli_bus = CliBus()
        context = SharedContext(config=mock_config, buses=[cli_bus])

        assert context.messagebus_buses == [cli_bus]

    def test_uses_provided_buses_when_given(self, mock_config):
        """When buses are provided, they should be used directly."""
        cli_bus = CliBus()
        context = SharedContext(config=mock_config, buses=[cli_bus])

        # Should contain exactly the bus we passed
        assert len(context.messagebus_buses) == 1
        assert context.messagebus_buses[0] is cli_bus

    def test_backward_compatible_loads_from_config_when_buses_none(self, mock_config):
        """When buses=None (default), should load from config like before."""
        with patch("picklebot.core.context.MessageBus.from_config") as mock_from_config:
            mock_from_config.return_value = []

            context = SharedContext(config=mock_config, buses=None)

            # Should have called from_config with the config
            mock_from_config.assert_called_once_with(mock_config)
            assert context.messagebus_buses == []

    def test_backward_compatible_default_behavior(self, mock_config):
        """Without buses parameter, should load from config (backward compat)."""
        with patch("picklebot.core.context.MessageBus.from_config") as mock_from_config:
            mock_from_config.return_value = []

            # Call without buses parameter - should work like before
            context = SharedContext(config=mock_config)

            mock_from_config.assert_called_once_with(mock_config)
            assert context.messagebus_buses == []

    def test_empty_buses_list_is_used_not_config(self, mock_config):
        """Empty list should be used, not fall back to config."""
        with patch("picklebot.core.context.MessageBus.from_config") as mock_from_config:
            mock_from_config.return_value = [
                MagicMock()
            ]  # Would return something if called

            # Pass empty list - should NOT call from_config
            context = SharedContext(config=mock_config, buses=[])

            mock_from_config.assert_not_called()
            assert context.messagebus_buses == []

    def test_multiple_buses_accepted(self, mock_config):
        """Multiple buses can be passed."""
        bus1 = CliBus()
        bus2 = CliBus()

        context = SharedContext(config=mock_config, buses=[bus1, bus2])

        assert len(context.messagebus_buses) == 2
        assert context.messagebus_buses[0] is bus1
        assert context.messagebus_buses[1] is bus2
