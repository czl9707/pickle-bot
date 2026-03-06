"""Tests for EventSource hierarchy."""

import pytest

from picklebot.core.events import (
    EventSource,
    AgentEventSource,
    CronEventSource,
    CliEventSource,
)
from picklebot.channel.telegram_channel import TelegramEventSource
from picklebot.channel.discord_channel import DiscordEventSource


class TestEventSourceBase:
    """Tests for EventSource ABC behavior."""

    def test_cannot_instantiate_abstract_base(self):
        """EventSource should not be directly instantiable."""
        with pytest.raises(TypeError):
            EventSource()

    def test_from_string_raises_on_unknown_namespace(self):
        """from_string should raise for unregistered namespace."""
        with pytest.raises(ValueError, match="Unknown source namespace"):
            EventSource.from_string("unknown:value")


class TestSourceRoundtrip:
    """Parametrized roundtrip tests for all EventSource types."""

    @pytest.mark.parametrize(
        "source_cls,args,expected_str,type_props",
        [
            (
                AgentEventSource,
                {"agent_id": "pickle"},
                "agent:pickle",
                {
                    "is_agent": True,
                    "is_platform": False,
                    "is_cron": False,
                    "platform_name": None,
                },
            ),
            (
                CronEventSource,
                {"cron_id": "daily-summary"},
                "cron:daily-summary",
                {
                    "is_agent": False,
                    "is_platform": False,
                    "is_cron": True,
                    "platform_name": None,
                },
            ),
            (
                TelegramEventSource,
                {"user_id": "12345", "chat_id": "67890"},
                "platform-telegram:12345:67890",
                {
                    "is_agent": False,
                    "is_platform": True,
                    "is_cron": False,
                    "platform_name": "telegram",
                },
            ),
            (
                DiscordEventSource,
                {"user_id": "12345", "channel_id": "67890"},
                "platform-discord:12345:67890",
                {
                    "is_agent": False,
                    "is_platform": True,
                    "is_cron": False,
                    "platform_name": "discord",
                },
            ),
            (
                CliEventSource,
                {},
                "platform-cli:cli-user",
                {
                    "is_agent": False,
                    "is_platform": True,
                    "is_cron": False,
                    "platform_name": "cli",
                },
            ),
        ],
    )
    def test_source_roundtrip(self, source_cls, args, expected_str, type_props):
        """Source should serialize/deserialize and have correct type properties."""
        # Create
        source = source_cls(**args)

        # Check serialization
        assert str(source) == expected_str

        # Check roundtrip via class method
        restored = source_cls.from_string(expected_str)
        for key, value in args.items():
            assert getattr(restored, key) == value

        # Check roundtrip via base class
        restored_via_base = EventSource.from_string(expected_str)
        assert isinstance(restored_via_base, source_cls)

        # Check type properties
        for prop, expected in type_props.items():
            assert getattr(source, prop) == expected
