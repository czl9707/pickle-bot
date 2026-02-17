"""Tests for MessageBusExecutor."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.core.messagebus_executor import MessageBusExecutor
from picklebot.messagebus.base import MessageBus


class MockBus(MessageBus):
    """Mock bus for testing."""

    def __init__(self, platform_name: str):
        self._platform_name = platform_name
        self.messages_sent: list[tuple[str, str]] = []
        self.started = False

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def start(self, on_message) -> None:
        self.started = True
        self._on_message = on_message

    async def send_message(self, content: str, user_id: str | None = None) -> None:
        self.messages_sent.append((user_id or "default", content))

    async def stop(self) -> None:
        self.started = False


@pytest.fixture
def executor_with_mock_bus(test_config):
    """Create MessageBusExecutor with mock bus."""
    # Create test agent for the executor (must match default_agent="test")
    agents_path = test_config.agents_path
    test_agent_dir = agents_path / "test"
    test_agent_dir.mkdir(parents=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    context = SharedContext(test_config)
    bus = MockBus("mock")
    executor = MessageBusExecutor(context, [bus])
    return executor, bus


@pytest.mark.anyio
async def test_messagebus_executor_enqueue_message(executor_with_mock_bus):
    """Test that messages are enqueued."""
    executor, _ = executor_with_mock_bus

    await executor._enqueue_message("Hello", "mock", "user123")

    assert executor.message_queue.qsize() == 1


@pytest.mark.anyio
async def test_messagebus_executor_processes_queue(executor_with_mock_bus):
    """Test that messages are processed from queue."""
    executor, bus = executor_with_mock_bus

    # Mock the session.chat method to avoid LLM calls
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test response"

        # Enqueue a message
        await executor._enqueue_message("Hello", "mock", "user123")

        # Start processing (will run in background)
        task = asyncio.create_task(executor._process_messages())

        # Wait for message to be processed
        await asyncio.sleep(0.5)

        # Stop the worker
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify message was sent
        assert len(bus.messages_sent) > 0
        assert bus.messages_sent[0] == ("user123", "Test response")


@pytest.mark.anyio
async def test_messagebus_executor_handles_errors(executor_with_mock_bus):
    """Test that errors during processing are handled gracefully."""
    executor, bus = executor_with_mock_bus

    # Mock session.chat to raise an error
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.side_effect = Exception("LLM error")

        # Enqueue a message
        await executor._enqueue_message("Hello", "mock", "user123")

        # Start processing (will run in background)
        task = asyncio.create_task(executor._process_messages())

        # Wait for message to be processed
        await asyncio.sleep(0.5)

        # Stop the worker
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify error message was sent
        assert len(bus.messages_sent) > 0
        assert "error" in bus.messages_sent[0][1].lower()


@pytest.mark.anyio
async def test_messagebus_executor_multiple_platforms(test_config):
    """Test that executor works with multiple platforms."""
    # Create test agent (must match default_agent="test")
    agents_path = test_config.agents_path
    test_agent_dir = agents_path / "test"
    test_agent_dir.mkdir(parents=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    context = SharedContext(test_config)

    bus1 = MockBus("telegram")
    bus2 = MockBus("discord")
    executor = MessageBusExecutor(context, [bus1, bus2])

    # Mock the session.chat method
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test response"

        # Enqueue messages for different platforms
        await executor._enqueue_message("Hello Telegram", "telegram", "user1")
        await executor._enqueue_message("Hello Discord", "discord", "user2")

        # Start processing
        task = asyncio.create_task(executor._process_messages())

        # Wait for messages to be processed
        await asyncio.sleep(0.5)

        # Stop the worker
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify messages were sent to correct platforms
        assert len(bus1.messages_sent) == 1
        assert bus1.messages_sent[0] == ("user1", "Test response")
        assert len(bus2.messages_sent) == 1
        assert bus2.messages_sent[0] == ("user2", "Test response")


class MockBusWithConfig(MessageBus):
    """Mock bus with config for whitelist testing."""

    def __init__(self, platform_name: str, allowed_user_ids: list[str] | None = None):
        self._platform_name = platform_name
        self.config = MagicMock()
        self.config.allowed_user_ids = allowed_user_ids or []
        self.messages_sent: list[tuple[str, str]] = []

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, content: str, user_id: str | None = None) -> None:
        self.messages_sent.append((user_id or "default", content))

    async def stop(self) -> None:
        pass


def _create_test_config_for_whitelist(tmp_path: Path):
    """Create a minimal test config for whitelist tests."""
    from picklebot.utils.config import Config

    config_file = tmp_path / "config.system.yaml"
    config_file.write_text(
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
    test_agent_dir.mkdir(parents=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    return Config.load(tmp_path)


@pytest.mark.anyio
async def test_messagebus_executor_whitelist_allows_listed_user(tmp_path: Path):
    """Messages from whitelisted users should be processed."""
    config = _create_test_config_for_whitelist(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
    executor = MessageBusExecutor(context, [bus])

    # Whitelisted user
    await executor._enqueue_message("Hello", "mock", "user123")

    assert executor.message_queue.qsize() == 1


@pytest.mark.anyio
async def test_messagebus_executor_whitelist_blocks_unlisted_user(tmp_path: Path):
    """Messages from non-whitelisted users should be ignored."""
    config = _create_test_config_for_whitelist(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
    executor = MessageBusExecutor(context, [bus])

    # Non-whitelisted user
    await executor._enqueue_message("Hello", "mock", "unknown_user")

    assert executor.message_queue.qsize() == 0


@pytest.mark.anyio
async def test_messagebus_executor_empty_whitelist_allows_all(tmp_path: Path):
    """When whitelist is empty, all users should be allowed."""
    config = _create_test_config_for_whitelist(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=[])
    executor = MessageBusExecutor(context, [bus])

    # Any user when whitelist is empty
    await executor._enqueue_message("Hello", "mock", "any_user")

    assert executor.message_queue.qsize() == 1
