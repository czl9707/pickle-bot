"""Tests for post_message tool factory."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from picklebot.tools.post_message_tool import create_post_message_tool
from picklebot.utils.config import Config, MessageBusConfig, TelegramConfig
from picklebot.core.events import OutboundEvent, EventType


def _make_context_with_messagebus(
    enabled: bool = True, default_platform: str = "telegram"
):
    """Helper to create a mock context with messagebus config."""
    from picklebot.core.context import SharedContext

    # Create minimal config
    tmp_path = Path("/tmp/test-picklebot")
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "config.user.yaml").write_text(
        """
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
default_agent: test-agent
"""
    )

    # Create test agent
    agents_path = tmp_path / "agents"
    test_agent_dir = agents_path / "test-agent"
    test_agent_dir.mkdir(parents=True, exist_ok=True)
    (test_agent_dir / "AGENT.md").write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant.
"""
    )

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


def _make_mock_session(
    session_id: str = "test-session-123", agent_id: str = "test-agent"
):
    """Helper to create a mock session."""
    mock_session = MagicMock()
    mock_session.session_id = session_id
    mock_session.agent_id = agent_id
    return mock_session


class TestCreatePostMessageTool:
    """Tests for create_post_message_tool factory function."""

    def test_returns_none_when_messagebus_disabled(self):
        """Should return None when messagebus is not enabled."""
        context = _make_context_with_messagebus(enabled=False)
        tool = create_post_message_tool(context)
        assert tool is None

    def test_creates_tool_with_correct_schema(self):
        """Should return a tool with correct name and parameters when messagebus is enabled."""
        context = _make_context_with_messagebus(enabled=True)
        tool = create_post_message_tool(context)

        assert tool is not None
        assert tool.name == "post_message"
        schema = tool.get_tool_schema()
        assert "content" in schema["function"]["parameters"]["properties"]
        assert "content" in schema["function"]["parameters"]["required"]


class TestPostMessageToolExecution:
    """Tests for post_message tool execution."""

    @pytest.mark.anyio
    async def test_uses_session_for_event(self):
        """Should use session info for session_id and source."""
        context = _make_context_with_messagebus(
            enabled=True, default_platform="telegram"
        )

        # Mock the eventbus.publish method
        original_publish = context.eventbus.publish
        context.eventbus.publish = AsyncMock()

        mock_session = _make_mock_session()
        tool = create_post_message_tool(context)
        assert tool is not None

        result = await tool.execute(session=mock_session, content="Hello from agent!")

        # Verify publish was called
        context.eventbus.publish.assert_called_once()
        call_args = context.eventbus.publish.call_args
        event = call_args[0][0]

        # Verify event uses session info
        assert isinstance(event, OutboundEvent)
        assert event.type == EventType.OUTBOUND
        assert event.session_id == "test-session-123"
        assert event.agent_id == "test-agent"
        assert event.source == "agent:test-agent"
        assert event.content == "Hello from agent!"

        # Verify result message
        assert "queued" in result.lower() or "success" in result.lower()

        # Restore
        context.eventbus.publish = original_publish

    @pytest.mark.anyio
    async def test_returns_error_on_exception(self):
        """Should return error message if publishing fails."""
        context = _make_context_with_messagebus(
            enabled=True, default_platform="telegram"
        )

        # Mock the eventbus.publish to raise an exception
        original_publish = context.eventbus.publish
        context.eventbus.publish = AsyncMock(side_effect=Exception("Test error"))

        mock_session = _make_mock_session()
        tool = create_post_message_tool(context)
        assert tool is not None

        result = await tool.execute(session=mock_session, content="Hello from agent!")

        # Verify error message
        assert "failed" in result.lower() or "error" in result.lower()

        # Restore
        context.eventbus.publish = original_publish
