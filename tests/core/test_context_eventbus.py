"""Tests for SharedContext EventBus integration."""

from picklebot.core.context import SharedContext
from picklebot.events.bus import EventBus
from picklebot.utils.config import Config


def test_shared_context_has_eventbus(tmp_path):
    """SharedContext should have an EventBus instance initialized."""
    # Create a minimal config file with all required fields
    config_file = tmp_path / "config.user.yaml"
    config_file.write_text(
        """default_agent: test-agent
llm:
  provider: openai
  model: gpt-4
  api_key: test
"""
    )

    config = Config.load(tmp_path)
    context = SharedContext(config)
    assert hasattr(context, "eventbus")
    assert isinstance(context.eventbus, EventBus)
