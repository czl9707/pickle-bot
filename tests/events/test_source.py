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
