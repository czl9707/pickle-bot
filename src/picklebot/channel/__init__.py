"""Channel implementations for different platforms."""

from picklebot.channel.base import Channel
from picklebot.channel.telegram_channel import TelegramChannel
from picklebot.channel.discord_channel import DiscordChannel

__all__ = ["Channel", "TelegramChannel", "DiscordChannel"]
