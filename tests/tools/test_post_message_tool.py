"""Tests for post_message tool factory."""

import pytest
from unittest.mock import AsyncMock
from pathlib import Path

from picklebot.tools.post_message_tool import create_post_message_tool
from picklebot.utils.config import Config, MessageBusConfig, TelegramConfig


def _make_context_with_messagebus(enabled: bool = True, default_platform: str = "telegram"):
    """Helper to create a mock context with messagebus config."""
    from picklebot.core.context import SharedContext

    # Create minimal config
    tmp_path = Path("/tmp/test-picklebot")
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "config.system.yaml").write_text("""
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
default_agent: test-agent
""")

    # Create test agent
    agents_path = tmp_path / "agents"
    test_agent_dir = agents_path / "test-agent"
    test_agent_dir.mkdir(parents=True, exist_ok=True)
    (test_agent_dir / "AGENT.md").write_text("""---
name: Test Agent
description: A test agent
---
You are a test assistant.
""")

    config = Config.load(tmp_path)

    # Override messagebus config
    if enabled:
        config.messagebus = MessageBusConfig(
            enabled=True,
            default_platform=default_platform,
            telegram=TelegramConfig(
                enabled=True,
                bot_token="test-token",
                default_chat_id="123456",
            ),
        )
    else:
        config.messagebus = MessageBusConfig(enabled=False)

    return SharedContext(config)


class TestCreatePostMessageTool:
    """Tests for create_post_message_tool factory function."""

    def test_returns_none_when_messagebus_disabled(self):
        """Should return None when messagebus is not enabled."""
        context = _make_context_with_messagebus(enabled=False)
        tool = create_post_message_tool(context)
        assert tool is None

    def test_returns_tool_when_messagebus_enabled(self):
        """Should return a tool when messagebus is enabled."""
        context = _make_context_with_messagebus(enabled=True)
        tool = create_post_message_tool(context)
        assert tool is not None
        assert tool.name == "post_message"

    def test_tool_has_correct_schema(self):
        """Tool should have correct name and parameters."""
        context = _make_context_with_messagebus(enabled=True)
        tool = create_post_message_tool(context)

        assert tool.name == "post_message"
        schema = tool.get_tool_schema()
        assert "content" in schema["function"]["parameters"]["properties"]
        assert "content" in schema["function"]["parameters"]["required"]


class TestPostMessageToolExecution:
    """Tests for post_message tool execution."""

    @pytest.mark.anyio
    async def test_sends_message_to_default_platform(self):
        """Should send message to default_platform with default_chat_id."""

        context = _make_context_with_messagebus(enabled=True, default_platform="telegram")

        # Find the telegram bus and mock its send_message
        telegram_bus = next(
            (b for b in context.messagebus_buses if b.platform_name == "telegram"), None
        )
        assert telegram_bus is not None

        # Mock send_message
        original_send = telegram_bus.send_message
        telegram_bus.send_message = AsyncMock()

        tool = create_post_message_tool(context)
        assert tool is not None

        result = await tool.execute(content="Hello from agent!")

        telegram_bus.send_message.assert_called_once_with(
            content="Hello from agent!", user_id=None
        )
        assert "sent" in result.lower() or "success" in result.lower()

        # Restore
        telegram_bus.send_message = original_send
