"""Tests for DiscordBus."""

import pytest
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import DiscordConfig


def test_discord_bus_platform_name():
    """Test that DiscordBus has correct platform name."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)
    assert bus.platform_name == "discord"


@pytest.mark.asyncio
async def test_discord_bus_start_stop():
    """Test that DiscordBus can start and stop."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)

    # Should not raise
    await bus.start(lambda msg, plat, uid: None)
    # Note: Discord bot needs event loop to fully start, so we just test it doesn't crash
    await bus.stop()
