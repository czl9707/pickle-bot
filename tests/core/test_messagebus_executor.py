"""Tests for MessageBusExecutor."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.core.messagebus_executor import MessageBusExecutor
from picklebot.messagebus.base import MessageBus


@dataclass
class MockContext:
    """Mock context for testing."""

    user_id: str
    chat_id: str


class MockBus(MessageBus[MockContext]):
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

    def is_allowed(self, context: MockContext) -> bool:
        return True  # Allow all in basic mock

    async def reply(self, content: str, context: MockContext) -> None:
        self.messages_sent.append((context.chat_id, content))

    async def post(self, content: str, target: str | None = None) -> None:
        self.messages_sent.append(("default", content))

    async def stop(self) -> None:
        self.started = False


class MockBusWithConfig(MessageBus[MockContext]):
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

    def is_allowed(self, context: MockContext) -> bool:
        if not self.config.allowed_user_ids:
            return True
        return context.user_id in self.config.allowed_user_ids

    async def reply(self, content: str, context: MockContext) -> None:
        self.messages_sent.append((context.chat_id, content))

    async def post(self, content: str, target: str | None = None) -> None:
        self.messages_sent.append(("default", content))

    async def stop(self) -> None:
        pass


def _create_test_agent(agents_path: Path) -> None:
    """Create a test agent for executor tests."""
    test_agent_dir = agents_path / "test"
    test_agent_dir.mkdir(parents=True, exist_ok=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )


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

    # Create test-agent directly (not using _create_test_agent which uses "test" id)
    test_agent_dir = tmp_path / "agents" / "test-agent"
    test_agent_dir.mkdir(parents=True, exist_ok=True)
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


@pytest.fixture
def executor_with_mock_bus(test_config):
    """Create MessageBusExecutor with mock bus."""
    _create_test_agent(test_config.agents_path)

    context = SharedContext(test_config)
    bus = MockBus("mock")
    executor = MessageBusExecutor(context, [bus])
    return executor, bus


class TestMessageEnqueue:
    """Tests for message queue operations."""

    @pytest.mark.anyio
    async def test_enqueue_message(self, executor_with_mock_bus):
        """Test that messages are enqueued."""
        executor, _ = executor_with_mock_bus

        ctx = MockContext(user_id="user123", chat_id="chat456")
        await executor._enqueue_message("Hello", "mock", ctx)

        assert executor.message_queue.qsize() == 1

    @pytest.mark.anyio
    async def test_whitelist_allows_listed_user(self, tmp_path: Path):
        """Messages from whitelisted users should be processed."""
        config = _create_test_config_for_whitelist(tmp_path)
        context = SharedContext(config)

        bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
        executor = MessageBusExecutor(context, [bus])

        ctx = MockContext(user_id="user123", chat_id="chat456")
        await executor._enqueue_message("Hello", "mock", ctx)

        assert executor.message_queue.qsize() == 1

    @pytest.mark.anyio
    async def test_whitelist_blocks_unlisted_user(self, tmp_path: Path):
        """Messages from non-whitelisted users should be ignored."""
        config = _create_test_config_for_whitelist(tmp_path)
        context = SharedContext(config)

        bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
        executor = MessageBusExecutor(context, [bus])

        ctx = MockContext(user_id="unknown_user", chat_id="chat456")
        await executor._enqueue_message("Hello", "mock", ctx)

        assert executor.message_queue.qsize() == 0

    @pytest.mark.anyio
    async def test_empty_whitelist_allows_all(self, tmp_path: Path):
        """When whitelist is empty, all users should be allowed."""
        config = _create_test_config_for_whitelist(tmp_path)
        context = SharedContext(config)

        bus = MockBusWithConfig("mock", allowed_user_ids=[])
        executor = MessageBusExecutor(context, [bus])

        ctx = MockContext(user_id="any_user", chat_id="chat456")
        await executor._enqueue_message("Hello", "mock", ctx)

        assert executor.message_queue.qsize() == 1


class TestMessageProcessing:
    """Tests for queue processing and LLM interaction."""

    @pytest.mark.anyio
    async def test_processes_queue(self, executor_with_mock_bus):
        """Test that messages are processed from queue and routed via frontend."""
        executor, bus = executor_with_mock_bus

        async def mock_chat_with_frontend(message: str, frontend) -> None:
            """Mock chat that calls frontend.show_message like real Agent."""
            await frontend.show_message("Test response")

        with patch.object(
            executor.session, "chat", side_effect=mock_chat_with_frontend
        ):
            ctx = MockContext(user_id="user123", chat_id="chat456")
            await executor._enqueue_message("Hello", "mock", ctx)

            task = asyncio.create_task(executor._process_messages())
            await asyncio.sleep(0.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            assert len(bus.messages_sent) > 0
            assert bus.messages_sent[0] == ("chat456", "Test response")

    @pytest.mark.anyio
    async def test_handles_errors(self, executor_with_mock_bus):
        """Test that errors during processing are handled gracefully."""
        executor, bus = executor_with_mock_bus

        async def mock_chat_error(message: str, frontend) -> None:
            """Mock chat that raises an error."""
            raise Exception("LLM error")

        with patch.object(
            executor.session, "chat", side_effect=mock_chat_error
        ):
            ctx = MockContext(user_id="user123", chat_id="chat456")
            await executor._enqueue_message("Hello", "mock", ctx)

            task = asyncio.create_task(executor._process_messages())
            await asyncio.sleep(0.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            assert len(bus.messages_sent) > 0
            assert "error" in bus.messages_sent[0][1].lower()


class TestMultiPlatform:
    """Tests for multi-platform routing."""

    @pytest.mark.anyio
    async def test_routes_to_correct_platform(self, test_config):
        """Test that executor routes messages to correct platforms via frontend."""
        _create_test_agent(test_config.agents_path)

        context = SharedContext(test_config)

        bus1 = MockBus("telegram")
        bus2 = MockBus("discord")
        executor = MessageBusExecutor(context, [bus1, bus2])

        async def mock_chat_with_frontend(message: str, frontend) -> None:
            """Mock chat that calls frontend.show_message like real Agent."""
            await frontend.show_message("Test response")

        with patch.object(
            executor.session, "chat", side_effect=mock_chat_with_frontend
        ):
            ctx1 = MockContext(user_id="user1", chat_id="chat1")
            ctx2 = MockContext(user_id="user2", chat_id="chat2")
            await executor._enqueue_message("Hello Telegram", "telegram", ctx1)
            await executor._enqueue_message("Hello Discord", "discord", ctx2)

            task = asyncio.create_task(executor._process_messages())
            await asyncio.sleep(0.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            assert len(bus1.messages_sent) == 1
            assert bus1.messages_sent[0] == ("chat1", "Test response")
            assert len(bus2.messages_sent) == 1
            assert bus2.messages_sent[0] == ("chat2", "Test response")
