# Post Message Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `post_message` tool that allows agents to proactively send messages to users via the default messaging platform.

**Architecture:** Add per-platform whitelist and default user config, modify MessageBus.send_message to use defaults, add whitelist check in executor, create post_message tool factory following skill_tool pattern.

**Tech Stack:** Pydantic for config validation, existing MessageBus abstraction, @tool decorator pattern

---

## Task 1: Config - Add Platform User Fields

**Files:**
- Modify: `src/picklebot/utils/config.py:31-43`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing tests for new config fields**

Add to `tests/utils/test_config.py`:

```python
class TestMessageBusUserFields:
    """Tests for messagebus user configuration fields."""

    def test_telegram_config_allows_user_fields(self, minimal_llm_config):
        """TelegramConfig should accept allowed_user_ids and default_user_id."""
        from picklebot.utils.config import TelegramConfig, MessageBusConfig

        telegram = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["123456"],
            default_user_id="123456",
        )
        assert telegram.allowed_user_ids == ["123456"]
        assert telegram.default_user_id == "123456"

    def test_discord_config_allows_user_fields(self, minimal_llm_config):
        """DiscordConfig should accept allowed_user_ids and default_user_id."""
        from picklebot.utils.config import DiscordConfig

        discord = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["789012"],
            default_user_id="789012",
        )
        assert discord.allowed_user_ids == ["789012"]
        assert discord.default_user_id == "789012"

    def test_user_fields_default_to_empty(self, minimal_llm_config):
        """User fields should have sensible defaults."""
        from picklebot.utils.config import TelegramConfig, DiscordConfig

        telegram = TelegramConfig(enabled=True, bot_token="test-token")
        assert telegram.allowed_user_ids == []
        assert telegram.default_user_id is None

        discord = DiscordConfig(enabled=True, bot_token="test-token")
        assert discord.allowed_user_ids == []
        assert discord.default_user_id is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_config.py::TestMessageBusUserFields -v`
Expected: FAIL with ValidationError or AttributeError

**Step 3: Add fields to TelegramConfig and DiscordConfig**

Modify `src/picklebot/utils/config.py`:

```python
class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_user_id: str | None = None


class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_user_id: str | None = None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_config.py::TestMessageBusUserFields -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add allowed_user_ids and default_user_id to platform configs"
```

---

## Task 2: MessageBus Base - Make user_id Optional

**Files:**
- Modify: `src/picklebot/messagebus/base.py:35-44`
- Test: `tests/messagebus/test_base.py` (new file)

**Step 1: Write the failing test for updated signature**

Create `tests/messagebus/test_base.py`:

```python
"""Tests for MessageBus base class."""

import pytest
from unittest.mock import AsyncMock
from picklebot.messagebus.base import MessageBus


class TestMessageBusSignature:
    """Tests for MessageBus abstract interface."""

    def test_send_message_user_id_is_optional(self):
        """send_message should have optional user_id parameter."""
        import inspect
        sig = inspect.signature(MessageBus.send_message)
        params = list(sig.parameters.keys())
        # Should have: self, content, user_id (with default)
        assert "content" in params
        assert "user_id" in params
        # user_id should have a default value
        user_id_param = sig.parameters["user_id"]
        assert user_id_param.default is not inspect.Parameter.empty
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_base.py -v`
Expected: FAIL - user_id currently required

**Step 3: Update MessageBus.send_message signature**

Modify `src/picklebot/messagebus/base.py`:

```python
@abstractmethod
async def send_message(self, content: str, user_id: str | None = None) -> None:
    """
    Send message to user on this platform.

    Args:
        content: Message content to send
        user_id: Platform-specific user identifier (uses default if not provided)
    """
    pass
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/base.py tests/messagebus/test_base.py
git commit -m "refactor(messagebus): make user_id optional in send_message"
```

---

## Task 3: TelegramBus - Implement Default User Fallback

**Files:**
- Modify: `src/picklebot/messagebus/telegram_bus.py:70-88`
- Test: `tests/messagebus/test_telegram_bus.py` (new file)

**Step 1: Write the failing test**

Create `tests/messagebus/test_telegram_bus.py`:

```python
"""Tests for TelegramBus."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.utils.config import TelegramConfig


class TestTelegramBusDefaultUser:
    """Tests for default user ID fallback."""

    def test_send_message_uses_default_user_when_not_provided(self):
        """send_message should use default_user_id when user_id is None."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="123456789",
        )
        bus = TelegramBus(config)

        # Verify config has the default
        assert bus.config.default_user_id == "123456789"

    @pytest.mark.anyio
    async def test_send_message_falls_back_to_default(self):
        """When user_id is None, should send to default_user_id."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="999888777",
        )
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        # Call without user_id
        await bus.send_message(content="Test message")

        # Should have called with default user_id
        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 999888777
        assert call_args.kwargs["text"] == "Test message"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`
Expected: FAIL - TypeError about missing user_id

**Step 3: Update TelegramBus.send_message**

Modify `src/picklebot/messagebus/telegram_bus.py`:

```python
async def send_message(self, content: str, user_id: str | None = None) -> None:
    """
    Send message to Telegram user.

    Args:
        content: Message content
        user_id: Telegram chat ID (uses default_user_id if not provided)
    """
    if not self.application:
        raise RuntimeError("TelegramBus not started")

    # Fall back to default user if not provided
    target_user = user_id or self.config.default_user_id
    if not target_user:
        raise ValueError("No user_id provided and no default_user_id configured")

    try:
        await self.application.bot.send_message(
            chat_id=int(target_user), text=content
        )
        logger.debug(f"Sent Telegram message to {target_user}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        raise
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/telegram_bus.py tests/messagebus/test_telegram_bus.py
git commit -m "feat(telegram): add default_user_id fallback to send_message"
```

---

## Task 4: DiscordBus - Implement Default User Fallback

**Files:**
- Modify: `src/picklebot/messagebus/discord_bus.py:87-107`
- Test: `tests/messagebus/test_discord_bus.py` (new file)

**Step 1: Write the failing test**

Create `tests/messagebus/test_discord_bus.py`:

```python
"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import DiscordConfig


class TestDiscordBusDefaultUser:
    """Tests for default user ID fallback."""

    @pytest.mark.anyio
    async def test_send_message_falls_back_to_default(self):
        """When user_id is None, should send to default_user_id."""
        config = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="111222333",
        )
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        # Call without user_id
        await bus.send_message(content="Test message")

        # Should have called with default user_id
        mock_client.get_channel.assert_called_once_with(111222333)
        mock_channel.send.assert_called_once_with("Test message")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`
Expected: FAIL - TypeError about missing user_id

**Step 3: Update DiscordBus.send_message**

Modify `src/picklebot/messagebus/discord_bus.py`:

```python
async def send_message(self, content: str, user_id: str | None = None) -> None:
    """
    Send message to Discord channel.

    Args:
        content: Message content
        user_id: Discord channel ID (uses default_user_id if not provided)
    """
    if not self.client:
        raise RuntimeError("DiscordBus not started")

    # Fall back to default user if not provided
    target_user = user_id or self.config.default_user_id
    if not target_user:
        raise ValueError("No user_id provided and no default_user_id configured")

    try:
        channel = self.client.get_channel(int(target_user))
        if not channel:
            raise ValueError(f"Channel {target_user} not found")

        await channel.send(content)
        logger.debug(f"Sent Discord message to {target_user}")
    except Exception as e:
        logger.error(f"Failed to send Discord message: {e}")
        raise
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/discord_bus.py tests/messagebus/test_discord_bus.py
git commit -m "feat(discord): add default_user_id fallback to send_message"
```

---

## Task 5: MessageBusExecutor - Add Whitelist Check

**Files:**
- Modify: `src/picklebot/core/messagebus_executor.py:51-63`
- Test: `tests/core/test_messagebus_executor.py`

**Step 1: Write the failing test**

Add to `tests/core/test_messagebus_executor.py`:

```python
class MockBusWithConfig(MessageBus):
    """Mock bus with config for whitelist testing."""

    def __init__(self, platform_name: str, allowed_user_ids: list[str] = None):
        self._platform_name = platform_name
        self.config = MagicMock()
        self.config.allowed_user_ids = allowed_user_ids or []
        self.messages_sent: list[tuple[str, str]] = []

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, content: str, user_id: str = None) -> None:
        self.messages_sent.append((user_id, content))

    async def stop(self) -> None:
        pass


@pytest.mark.anyio
async def test_messagebus_executor_whitelist_allows_listed_user(tmp_path: Path):
    """Messages from whitelisted users should be processed."""
    from picklebot.core.context import SharedContext

    config = _create_test_config(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
    executor = MessageBusExecutor(context, [bus])

    # Whitelisted user
    await executor._enqueue_message("Hello", "mock", "user123")

    assert executor.message_queue.qsize() == 1


@pytest.mark.anyio
async def test_messagebus_executor_whitelist_blocks_unlisted_user(tmp_path: Path):
    """Messages from non-whitelisted users should be ignored."""
    from picklebot.core.context import SharedContext

    config = _create_test_config(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=["user123"])
    executor = MessageBusExecutor(context, [bus])

    # Non-whitelisted user
    await executor._enqueue_message("Hello", "mock", "unknown_user")

    assert executor.message_queue.qsize() == 0


@pytest.mark.anyio
async def test_messagebus_executor_empty_whitelist_allows_all(tmp_path: Path):
    """When whitelist is empty, all users should be allowed."""
    from picklebot.core.context import SharedContext

    config = _create_test_config(tmp_path)
    context = SharedContext(config)

    bus = MockBusWithConfig("mock", allowed_user_ids=[])
    executor = MessageBusExecutor(context, [bus])

    # Any user when whitelist is empty
    await executor._enqueue_message("Hello", "mock", "any_user")

    assert executor.message_queue.qsize() == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_messagebus_executor.py::test_messagebus_executor_whitelist -v`
Expected: FAIL - whitelist not implemented

**Step 3: Add whitelist check to _enqueue_message**

Modify `src/picklebot/core/messagebus_executor.py`:

```python
async def _enqueue_message(
    self, message: str, platform: str, user_id: str
) -> None:
    """
    Add incoming message to queue (called by buses).

    Args:
        message: User message content
        platform: Platform identifier
        user_id: Platform-specific user ID
    """
    bus = self.bus_map[platform]

    # Check whitelist (empty list allows all)
    if bus.config.allowed_user_ids and user_id not in bus.config.allowed_user_ids:
        logger.info(f"Ignored message from non-whitelisted user {platform}/{user_id}")
        return

    await self.message_queue.put((message, platform, user_id))
    logger.debug(f"Enqueued message from {platform}/{user_id}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/messagebus_executor.py tests/core/test_messagebus_executor.py
git commit -m "feat(messagebus): add whitelist check for incoming messages"
```

---

## Task 6: Create Post Message Tool Factory

**Files:**
- Create: `src/picklebot/tools/post_message_tool.py`
- Test: `tests/tools/test_post_message_tool.py` (new file)

**Step 1: Write the failing tests**

Create `tests/tools/test_post_message_tool.py`:

```python
"""Tests for post_message tool factory."""

import pytest
from unittest.mock import MagicMock, AsyncMock
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
                default_user_id="123456",
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
        """Should send message to default_platform with default_user_id."""
        from picklebot.messagebus.base import MessageBus

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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: FAIL - module not found

**Step 3: Create the post_message_tool module**

Create `src/picklebot/tools/post_message_tool.py`:

```python
"""Post message tool factory for agent-initiated messaging."""

from typing import TYPE_CHECKING

from picklebot.tools.base import BaseTool, tool

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


def create_post_message_tool(context: "SharedContext") -> BaseTool | None:
    """
    Factory to create post_message tool.

    Args:
        context: SharedContext with messagebus configuration

    Returns:
        Tool for posting messages, or None if messagebus not enabled
    """
    config = context.config

    # Return None if messagebus not enabled
    if not config.messagebus.enabled:
        return None

    # Get default platform
    default_platform = config.messagebus.default_platform
    if not default_platform:
        return None

    # Find the default platform bus
    bus_map = {bus.platform_name: bus for bus in context.messagebus_buses}
    default_bus = bus_map.get(default_platform)

    if not default_bus:
        return None

    @tool(
        name="post_message",
        description="Send a message to the user via the default messaging platform. Use this to proactively notify the user about completed tasks, cron results, or important updates.",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send to the user",
                }
            },
            "required": ["content"],
        },
    )
    async def post_message(content: str) -> str:
        """
        Send a message to the default user on the default platform.

        Args:
            content: Message content to send

        Returns:
            Success or error message
        """
        try:
            await default_bus.send_message(content=content)
            return f"Message sent successfully to {default_platform}"
        except Exception as e:
            return f"Failed to send message: {e}"

    return post_message
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/post_message_tool.py tests/tools/test_post_message_tool.py
git commit -m "feat(tools): add post_message tool for agent-initiated messaging"
```

---

## Task 7: Register Post Message Tool in Agent

**Files:**
- Modify: `src/picklebot/core/agent.py:12-13,49,62`
- Test: Integration test via existing agent tests

**Step 1: Update imports in agent.py**

Modify `src/picklebot/core/agent.py`:

```python
from picklebot.tools.skill_tool import create_skill_tool
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.tools.post_message_tool import create_post_message_tool
```

**Step 2: Add registration method and call**

Add after `_register_subagent_tool` method:

```python
def _register_subagent_tool(self) -> None:
    """Register the subagent dispatch tool if agents are available."""
    subagent_tool = create_subagent_dispatch_tool(self.agent_def.id, self.context)
    if subagent_tool:
        self.tools.register(subagent_tool)

def _register_post_message_tool(self) -> None:
    """Register the post_message tool if messagebus is enabled."""
    post_tool = create_post_message_tool(self.context)
    if post_tool:
        self.tools.register(post_tool)
```

**Step 3: Call the registration in __init__**

Modify `__init__` to add the call:

```python
def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
    self.agent_def = agent_def
    self.context = context
    self.tools = ToolRegistry.with_builtins()
    self.llm = LLMProvider.from_config(agent_def.llm)

    # Add skill tool if allowed
    if agent_def.allow_skills:
        self._register_skill_tool()

    # Add subagent dispatch tool
    self._register_subagent_tool()

    # Add post_message tool
    self._register_post_message_tool()
```

**Step 4: Run all tests to verify nothing breaks**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "feat(agent): register post_message tool when messagebus enabled"
```

---

## Task 8: Update MessageBusExecutor for New Signature

**Files:**
- Modify: `src/picklebot/core/messagebus_executor.py:74`

**Step 1: Update send_message call to use keyword argument**

The signature changed from `send_message(user_id, content)` to `send_message(content, user_id=None)`. Update the call:

```python
await self.bus_map[platform].send_message(content=response, user_id=user_id)
```

And the error message call:

```python
await self.bus_map[platform].send_message(
    content="Sorry, I encountered an error processing your message.",
    user_id=user_id,
)
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/messagebus_executor.py
git commit -m "refactor(messagebus): update send_message calls to use keyword args"
```

---

## Task 9: Final Verification

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting and type checking**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address linting issues"
```
