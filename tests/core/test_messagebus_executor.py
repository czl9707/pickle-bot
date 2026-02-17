"""Tests for MessageBusExecutor."""

import asyncio
from unittest.mock import AsyncMock, patch

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

    async def send_message(self, user_id: str, content: str) -> None:
        self.messages_sent.append((user_id, content))

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
