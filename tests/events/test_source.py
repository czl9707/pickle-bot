"""Tests for EventSource hierarchy."""

import pytest

from picklebot.core.events import EventSource


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


class TestAgentEventSource:
    """Tests for AgentEventSource."""

    def test_string_roundtrip(self):
        """Agent source should serialize and deserialize correctly."""
        from picklebot.core.events import AgentEventSource

        original = AgentEventSource(agent_id="pickle")
        serialized = str(original)
        deserialized = AgentEventSource.from_string(serialized)

        assert serialized == "agent:pickle"
        assert deserialized.agent_id == "pickle"

    def test_type_properties(self):
        """Agent source should have correct type properties."""
        from picklebot.core.events import AgentEventSource

        source = AgentEventSource(agent_id="pickle")
        assert source.is_agent is True
        assert source.is_platform is False
        assert source.is_cron is False
        assert source.platform_name is None


class TestCronEventSource:
    """Tests for CronEventSource."""

    def test_string_roundtrip(self):
        """Cron source should serialize and deserialize correctly."""
        from picklebot.core.events import CronEventSource

        original = CronEventSource(cron_id="daily-summary")
        serialized = str(original)
        deserialized = CronEventSource.from_string(serialized)

        assert serialized == "cron:daily-summary"
        assert deserialized.cron_id == "daily-summary"

    def test_type_properties(self):
        """Cron source should have correct type properties."""
        from picklebot.core.events import CronEventSource

        source = CronEventSource(cron_id="daily-summary")
        assert source.is_cron is True
        assert source.is_agent is False
        assert source.is_platform is False
        assert source.platform_name is None


class TestTelegramEventSource:
    """Tests for TelegramEventSource."""

    def test_string_roundtrip(self):
        """Telegram source should serialize and deserialize correctly."""
        from picklebot.messagebus.telegram_bus import TelegramEventSource

        original = TelegramEventSource(user_id="12345", chat_id="67890")
        serialized = str(original)
        deserialized = TelegramEventSource.from_string(serialized)

        assert serialized == "platform-telegram:12345:67890"
        assert deserialized.user_id == "12345"
        assert deserialized.chat_id == "67890"

    def test_type_properties(self):
        """Telegram source should have correct type properties."""
        from picklebot.messagebus.telegram_bus import TelegramEventSource

        source = TelegramEventSource(user_id="12345", chat_id="67890")
        assert source.is_platform is True
        assert source.is_agent is False
        assert source.is_cron is False
        assert source.platform_name == "telegram"

    def test_via_base_from_string(self):
        """Telegram source should be parseable via EventSource.from_string."""
        from picklebot.core.events import EventSource
        from picklebot.messagebus.telegram_bus import TelegramEventSource

        source = EventSource.from_string("platform-telegram:12345:67890")
        assert isinstance(source, TelegramEventSource)
        assert source.user_id == "12345"
        assert source.chat_id == "67890"


class TestDiscordEventSource:
    """Tests for DiscordEventSource."""

    def test_string_roundtrip(self):
        """Discord source should serialize and deserialize correctly."""
        from picklebot.messagebus.discord_bus import DiscordEventSource

        original = DiscordEventSource(user_id="12345", channel_id="67890")
        serialized = str(original)
        deserialized = DiscordEventSource.from_string(serialized)

        assert serialized == "platform-discord:12345:67890"
        assert deserialized.user_id == "12345"
        assert deserialized.channel_id == "67890"

    def test_type_properties(self):
        """Discord source should have correct type properties."""
        from picklebot.messagebus.discord_bus import DiscordEventSource

        source = DiscordEventSource(user_id="12345", channel_id="67890")
        assert source.is_platform is True
        assert source.platform_name == "discord"


class TestCliEventSource:
    """Tests for CliEventSource."""

    def test_string_roundtrip(self):
        """CLI source should serialize and deserialize correctly."""
        from picklebot.core.events import CliEventSource

        original = CliEventSource()
        serialized = str(original)
        deserialized = CliEventSource.from_string(serialized)

        assert serialized == "platform-cli:cli-user"
        assert isinstance(deserialized, CliEventSource)

    def test_type_properties(self):
        """CLI source should have correct type properties."""
        from picklebot.core.events import CliEventSource

        source = CliEventSource()
        assert source.is_platform is True
        assert source.platform_name == "cli"
