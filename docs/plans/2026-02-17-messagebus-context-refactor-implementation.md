# MessageBus Context Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor MessageBus to use platform-specific contexts with clear semantics for whitelisting and messaging.

**Architecture:** Generic MessageBus interface with typed context classes. Each platform extracts user_id (for whitelisting) and chat_id/channel_id (for replying) separately. The executor delegates whitelist checks and reply logic to each bus.

**Tech Stack:** Python dataclasses, typing generics, pytest, unittest.mock

---

## Task 1: Update Config Models

**Files:**
- Modify: `src/picklebot/utils/config.py:31-48`
- Modify: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py`:

```python
class TestConfigDefaultChatId:
    """Tests for default_chat_id config field."""

    def test_telegram_config_has_default_chat_id(self):
        """TelegramConfig should have default_chat_id field."""
        from picklebot.utils.config import TelegramConfig

        config = TelegramConfig(
            bot_token="test-token",
            default_chat_id="123456",
        )
        assert config.default_chat_id == "123456"

    def test_discord_config_has_default_chat_id(self):
        """DiscordConfig should have default_chat_id field."""
        from picklebot.utils.config import DiscordConfig

        config = DiscordConfig(
            bot_token="test-token",
            default_chat_id="789012",
        )
        assert config.default_chat_id == "789012"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestConfigDefaultChatId -v`
Expected: FAIL with AttributeError or ValidationError

**Step 3: Update config models**

In `src/picklebot/utils/config.py`, rename `default_user_id` to `default_chat_id` in both `TelegramConfig` and `DiscordConfig`:

```python
class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None  # Renamed from default_user_id


class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None  # Renamed from default_user_id
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestConfigDefaultChatId -v`
Expected: PASS

**Step 5: Update existing tests**

Update any tests that reference `default_user_id`:

Run: `uv run pytest tests/ -v -k "default_user"`
Expected: See which tests fail

Update the failing tests to use `default_chat_id` instead.

**Step 6: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "refactor(config): rename default_user_id to default_chat_id"
```

---

## Task 2: Create Context Dataclasses

**Files:**
- Modify: `src/picklebot/messagebus/base.py`
- Modify: `tests/messagebus/test_base.py`

**Step 1: Write the failing test**

Add to `tests/messagebus/test_base.py`:

```python
class TestContextDataclasses:
    """Tests for platform context dataclasses."""

    def test_telegram_context_fields(self):
        """TelegramContext should have user_id and chat_id."""
        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="111", chat_id="222")
        assert ctx.user_id == "111"
        assert ctx.chat_id == "222"

    def test_discord_context_fields(self):
        """DiscordContext should have user_id and channel_id."""
        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="333", channel_id="444")
        assert ctx.user_id == "333"
        assert ctx.channel_id == "444"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_base.py::TestContextDataclasses -v`
Expected: FAIL with ImportError

**Step 3: Add context dataclasses**

In `src/picklebot/messagebus/base.py`, add at the top after imports:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class TelegramContext:
    """Context for Telegram messages."""

    user_id: str  # from_user.id - for whitelisting
    chat_id: str  # effective_chat.id - for replying


@dataclass
class DiscordContext:
    """Context for Discord messages."""

    user_id: str  # author.id - for whitelisting
    channel_id: str  # channel.id - for replying
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_base.py::TestContextDataclasses -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/base.py tests/messagebus/test_base.py
git commit -m "feat(messagebus): add TelegramContext and DiscordContext dataclasses"
```

---

## Task 3: Update MessageBus Base Interface

**Files:**
- Modify: `src/picklebot/messagebus/base.py`
- Modify: `tests/messagebus/test_base.py`

**Step 1: Write the failing test**

Add to `tests/messagebus/test_base.py`:

```python
from typing import Any
from abc import ABC


class TestMessageBusGenericInterface:
    """Tests for generic MessageBus interface."""

    def test_messagebus_is_generic(self):
        """MessageBus should be a Generic class."""
        from picklebot.messagebus.base import MessageBus

        # Should have generic type parameter
        assert hasattr(MessageBus, "__orig_bases__")

    def test_messagebus_has_is_allowed_method(self):
        """MessageBus should have is_allowed abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        # Check is_allowed is an abstract method
        assert hasattr(MessageBus, "is_allowed")
        sig = inspect.signature(MessageBus.is_allowed)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "context" in params

    def test_messagebus_has_reply_method(self):
        """MessageBus should have reply abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        assert hasattr(MessageBus, "reply")
        sig = inspect.signature(MessageBus.reply)
        params = list(sig.parameters.keys())
        assert "content" in params
        assert "context" in params

    def test_messagebus_has_post_method(self):
        """MessageBus should have post abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        assert hasattr(MessageBus, "post")
        sig = inspect.signature(MessageBus.post)
        params = list(sig.parameters.keys())
        assert "content" in params
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_base.py::TestMessageBusGenericInterface -v`
Expected: FAIL (methods don't exist yet)

**Step 3: Update MessageBus interface**

Replace the `MessageBus` class in `src/picklebot/messagebus/base.py`:

```python
class MessageBus(ABC, Generic[T]):
    """Abstract base for messaging platforms with platform-specific context."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Platform identifier.

        Returns:
            Platform name (e.g., 'telegram', 'discord')
        """
        pass

    @abstractmethod
    async def start(self, on_message: Callable[[str, T], Awaitable[None]]) -> None:
        """
        Start listening for messages.

        Args:
            on_message: Callback async function(message: str, context: T)
        """
        pass

    @abstractmethod
    def is_allowed(self, context: T) -> bool:
        """
        Check if sender is whitelisted.

        Args:
            context: Platform-specific message context

        Returns:
            True if sender is allowed
        """
        pass

    @abstractmethod
    async def reply(self, content: str, context: T) -> None:
        """
        Reply to incoming message.

        Args:
            content: Message content to send
            context: Platform-specific context from incoming message
        """
        pass

    @abstractmethod
    async def post(self, content: str, target: str | None = None) -> None:
        """
        Post proactive message to default destination or specific target.

        Args:
            content: Message content to send
            target: Optional target (e.g., "user:123", "channel:456")
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass

    @staticmethod
    def from_config(config: Config) -> list["MessageBus"]:
        """
        Create message bus instances from configuration.

        Args:
            config: Message bus configuration

        Returns:
            List of configured message bus instances
        """
        # Inline imports to avoid circular dependency
        from picklebot.messagebus.telegram_bus import TelegramBus
        from picklebot.messagebus.discord_bus import DiscordBus

        buses: list["MessageBus"] = []
        bus_config = config.messagebus
        if bus_config.telegram and bus_config.telegram.enabled:
            buses.append(TelegramBus(bus_config.telegram))

        if bus_config.discord and bus_config.discord.enabled:
            buses.append(DiscordBus(bus_config.discord))

        return buses
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_base.py::TestMessageBusGenericInterface -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/base.py tests/messagebus/test_base.py
git commit -m "refactor(messagebus): add generic interface with is_allowed, reply, post"
```

---

## Task 4: Update TelegramBus Implementation

**Files:**
- Modify: `src/picklebot/messagebus/telegram_bus.py`
- Modify: `tests/messagebus/test_telegram_bus.py`

**Step 4.1: Write failing test for is_allowed**

Add to `tests/messagebus/test_telegram_bus.py`:

```python
class TestTelegramBusIsAllowed:
    """Tests for TelegramBus.is_allowed method."""

    def test_is_allowed_returns_true_for_whitelisted_user(self):
        """is_allowed should return True for whitelisted user."""
        config = TelegramConfig(
            bot_token="test-token",
            allowed_user_ids=["user123"],
        )
        bus = TelegramBus(config)
        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="user123", chat_id="chat456")
        assert bus.is_allowed(ctx) is True

    def test_is_allowed_returns_false_for_non_whitelisted_user(self):
        """is_allowed should return False for non-whitelisted user."""
        config = TelegramConfig(
            bot_token="test-token",
            allowed_user_ids=["user123"],
        )
        bus = TelegramBus(config)
        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="unknown", chat_id="chat456")
        assert bus.is_allowed(ctx) is False

    def test_is_allowed_returns_true_when_whitelist_empty(self):
        """is_allowed should return True when whitelist is empty."""
        config = TelegramConfig(
            bot_token="test-token",
            allowed_user_ids=[],
        )
        bus = TelegramBus(config)
        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="anyone", chat_id="chat456")
        assert bus.is_allowed(ctx) is True
```

**Step 4.2: Run test, implement is_allowed**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py::TestTelegramBusIsAllowed -v`
Expected: FAIL

Add to `TelegramBus` class:

```python
def is_allowed(self, context: "TelegramContext") -> bool:
    """Check if sender is whitelisted."""
    if not self.config.allowed_user_ids:
        return True
    return context.user_id in self.config.allowed_user_ids
```

**Step 4.3: Write failing test for reply**

Add to `tests/messagebus/test_telegram_bus.py`:

```python
class TestTelegramBusReply:
    """Tests for TelegramBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_chat_id(self):
        """reply should send to context.chat_id."""
        config = TelegramConfig(bot_token="test-token")
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="user123", chat_id="chat456")
        await bus.reply(content="Test reply", context=ctx)

        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 456
        assert call_args.kwargs["text"] == "Test reply"
```

**Step 4.4: Run test, implement reply**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py::TestTelegramBusReply -v`
Expected: FAIL

Add to `TelegramBus` class:

```python
async def reply(self, content: str, context: "TelegramContext") -> None:
    """Reply to incoming message."""
    if not self.application:
        raise RuntimeError("TelegramBus not started")

    try:
        await self.application.bot.send_message(
            chat_id=int(context.chat_id), text=content
        )
        logger.debug(f"Sent Telegram reply to {context.chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram reply: {e}")
        raise
```

**Step 4.5: Write failing test for post**

Add to `tests/messagebus/test_telegram_bus.py`:

```python
class TestTelegramBusPost:
    """Tests for TelegramBus.post method."""

    @pytest.mark.anyio
    async def test_post_sends_to_default_chat_id(self):
        """post should send to config.default_chat_id."""
        config = TelegramConfig(bot_token="test-token", default_chat_id="999888")
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        await bus.post(content="Proactive message")

        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 999888

    @pytest.mark.anyio
    async def test_post_raises_when_no_default_chat_id(self):
        """post should raise when no default_chat_id configured."""
        config = TelegramConfig(bot_token="test-token", default_chat_id=None)
        bus = TelegramBus(config)

        bus.application = MagicMock()  # Mark as started

        with pytest.raises(ValueError, match="No default_chat_id configured"):
            await bus.post(content="Test")
```

**Step 4.6: Run test, implement post**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py::TestTelegramBusPost -v`
Expected: FAIL

Add to `TelegramBus` class:

```python
async def post(self, content: str, target: str | None = None) -> None:
    """Post proactive message to default_chat_id."""
    if not self.application:
        raise RuntimeError("TelegramBus not started")

    # For now, ignore target parameter (future: support "user:123" format)
    if not self.config.default_chat_id:
        raise ValueError("No default_chat_id configured")

    try:
        await self.application.bot.send_message(
            chat_id=int(self.config.default_chat_id), text=content
        )
        logger.debug(f"Sent Telegram post to {self.config.default_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram post: {e}")
        raise
```

**Step 4.7: Update start method to extract proper context**

Update the `start` method in `TelegramBus` to use `from_user.id` for user_id:

```python
async def start(
    self, on_message: Callable[[str, "TelegramContext"], Awaitable[None]]
) -> None:
    """Start listening for Telegram messages."""
    logger.info(f"Message bus enabled with platform: {self.platform_name}")
    self.application = Application.builder().token(self.config.bot_token).build()

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming Telegram message."""
        if update.message and update.message.text and update.effective_chat:
            # Extract user_id (the person) and chat_id (the conversation)
            user_id = str(update.message.from_user.id)
            chat_id = str(update.effective_chat.id)
            message = update.message.text

            logger.info(f"Received Telegram message from user {user_id} in chat {chat_id}")

            ctx = TelegramContext(user_id=user_id, chat_id=chat_id)

            try:
                await on_message(message, ctx)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

    # Add message handler
    handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    self.application.add_handler(handler)

    # Start the bot
    await self.application.initialize()
    await self.application.start()
    if self.application.updater:
        await self.application.updater.start_polling()

    logger.info("TelegramBus started")
```

**Step 4.8: Remove old send_message method**

Delete the `send_message` method from `TelegramBus`.

**Step 4.9: Update type hints at top of file**

Add import for `TelegramContext`:

```python
from picklebot.messagebus.base import MessageBus, TelegramContext
```

**Step 4.10: Run all telegram tests**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`
Expected: PASS (after updating existing tests that used send_message)

**Step 4.11: Commit**

```bash
git add src/picklebot/messagebus/telegram_bus.py tests/messagebus/test_telegram_bus.py
git commit -m "refactor(telegram): implement context-based is_allowed, reply, post"
```

---

## Task 5: Update DiscordBus Implementation

**Files:**
- Modify: `src/picklebot/messagebus/discord_bus.py`
- Modify: `tests/messagebus/test_discord_bus.py`

**Step 5.1: Write failing test for is_allowed**

Add to `tests/messagebus/test_discord_bus.py`:

```python
class TestDiscordBusIsAllowed:
    """Tests for DiscordBus.is_allowed method."""

    def test_is_allowed_returns_true_for_whitelisted_user(self):
        """is_allowed should return True for whitelisted user."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=["user123"],
        )
        bus = DiscordBus(config)
        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="user123", channel_id="channel456")
        assert bus.is_allowed(ctx) is True

    def test_is_allowed_returns_false_for_non_whitelisted_user(self):
        """is_allowed should return False for non-whitelisted user."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=["user123"],
        )
        bus = DiscordBus(config)
        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="unknown", channel_id="channel456")
        assert bus.is_allowed(ctx) is False

    def test_is_allowed_returns_true_when_whitelist_empty(self):
        """is_allowed should return True when whitelist is empty."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=[],
        )
        bus = DiscordBus(config)
        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="anyone", channel_id="channel456")
        assert bus.is_allowed(ctx) is True
```

**Step 5.2: Run test, implement is_allowed**

Run: `uv run pytest tests/messagebus/test_discord_bus.py::TestDiscordBusIsAllowed -v`
Expected: FAIL

Add to `DiscordBus` class:

```python
def is_allowed(self, context: "DiscordContext") -> bool:
    """Check if sender is whitelisted."""
    if not self.config.allowed_user_ids:
        return True
    return context.user_id in self.config.allowed_user_ids
```

**Step 5.3: Write failing test for reply**

Add to `tests/messagebus/test_discord_bus.py`:

```python
class TestDiscordBusReply:
    """Tests for DiscordBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_channel_id(self):
        """reply should send to context.channel_id."""
        config = DiscordConfig(bot_token="test-token")
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="user123", channel_id="channel456")
        await bus.reply(content="Test reply", context=ctx)

        mock_client.get_channel.assert_called_once_with(456)
        mock_channel.send.assert_called_once_with("Test reply")
```

**Step 5.4: Run test, implement reply**

Run: `uv run pytest tests/messagebus/test_discord_bus.py::TestDiscordBusReply -v`
Expected: FAIL

Add to `DiscordBus` class:

```python
async def reply(self, content: str, context: "DiscordContext") -> None:
    """Reply to incoming message in the same channel."""
    if not self.client:
        raise RuntimeError("DiscordBus not started")

    try:
        channel = self.client.get_channel(int(context.channel_id))
        if not channel:
            raise ValueError(f"Channel {context.channel_id} not found")

        await channel.send(content)
        logger.debug(f"Sent Discord reply to {context.channel_id}")
    except Exception as e:
        logger.error(f"Failed to send Discord reply: {e}")
        raise
```

**Step 5.5: Write failing test for post**

Add to `tests/messagebus/test_discord_bus.py`:

```python
class TestDiscordBusPost:
    """Tests for DiscordBus.post method."""

    @pytest.mark.anyio
    async def test_post_sends_to_default_chat_id(self):
        """post should send to config.default_chat_id."""
        config = DiscordConfig(bot_token="test-token", default_chat_id="999888")
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        await bus.post(content="Proactive message")

        mock_client.get_channel.assert_called_once_with(999888)
        mock_channel.send.assert_called_once_with("Proactive message")

    @pytest.mark.anyio
    async def test_post_raises_when_no_default_chat_id(self):
        """post should raise when no default_chat_id configured."""
        config = DiscordConfig(bot_token="test-token", default_chat_id=None)
        bus = DiscordBus(config)

        bus.client = MagicMock()  # Mark as started

        with pytest.raises(ValueError, match="No default_chat_id configured"):
            await bus.post(content="Test")
```

**Step 5.6: Run test, implement post**

Run: `uv run pytest tests/messagebus/test_discord_bus.py::TestDiscordBusPost -v`
Expected: FAIL

Add to `DiscordBus` class:

```python
async def post(self, content: str, target: str | None = None) -> None:
    """Post proactive message to default_chat_id."""
    if not self.client:
        raise RuntimeError("DiscordBus not started")

    # For now, ignore target parameter (future: support "user:123" or "channel:456")
    if not self.config.default_chat_id:
        raise ValueError("No default_chat_id configured")

    try:
        channel = self.client.get_channel(int(self.config.default_chat_id))
        if not channel:
            raise ValueError(f"Channel {self.config.default_chat_id} not found")

        await channel.send(content)
        logger.debug(f"Sent Discord post to {self.config.default_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Discord post: {e}")
        raise
```

**Step 5.7: Update start method to extract proper context**

Update the `start` method in `DiscordBus` to use `author.id` for user_id:

```python
async def start(
    self, on_message: Callable[[str, "DiscordContext"], Awaitable[None]]
) -> None:
    """Start listening for Discord messages."""
    logger.info(f"Message bus enabled with platform: {self.platform_name}")

    # Configure intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True

    self.client = discord.Client(intents=intents)

    @self.client.event
    async def _on_discord_message(message: discord.Message):
        """Handle incoming Discord message."""
        # Ignore bot's own messages
        if message.author == self.client.user:
            return

        # Check channel restriction (optional)
        if (
            self.config.channel_id
            and str(message.channel.id) != self.config.channel_id
        ):
            return

        # Only handle text messages
        if not message.content:
            return

        # Extract user_id (the person) and channel_id (the channel)
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        content = message.content

        logger.info(f"Received Discord message from user {user_id} in channel {channel_id}")

        ctx = DiscordContext(user_id=user_id, channel_id=channel_id)

        try:
            await on_message(content, ctx)
        except Exception as e:
            logger.error(f"Error in message callback: {e}")

    # Start the bot in background
    asyncio.create_task(self.client.start(self.config.bot_token))

    # Wait a moment for client to initialize
    await asyncio.sleep(0.5)

    logger.info("DiscordBus started")
```

**Step 5.8: Remove old send_message method**

Delete the `send_message` method from `DiscordBus`.

**Step 5.9: Update type hints at top of file**

Add import for `DiscordContext`:

```python
from picklebot.messagebus.base import MessageBus, DiscordContext
```

**Step 5.10: Run all discord tests**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`
Expected: PASS (after updating existing tests that used send_message)

**Step 5.11: Commit**

```bash
git add src/picklebot/messagebus/discord_bus.py tests/messagebus/test_discord_bus.py
git commit -m "refactor(discord): implement context-based is_allowed, reply, post"
```

---

## Task 6: Update MessageBusExecutor

**Files:**
- Modify: `src/picklebot/core/messagebus_executor.py`
- Modify: `tests/core/test_messagebus_executor.py`

**Step 6.1: Write failing test for new interface**

Update `MockBus` classes in `tests/core/test_messagebus_executor.py`:

```python
from typing import Any
from dataclasses import dataclass


@dataclass
class MockContext:
    """Mock context for testing."""

    user_id: str
    chat_id: str


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

    def is_allowed(self, context: MockContext) -> bool:
        return True  # Allow all in basic mock

    async def reply(self, content: str, context: MockContext) -> None:
        self.messages_sent.append((context.chat_id, content))

    async def post(self, content: str, target: str | None = None) -> None:
        self.messages_sent.append(("default", content))

    async def stop(self) -> None:
        self.started = False


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
```

**Step 6.2: Run tests to see what fails**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: Some tests fail due to interface changes

**Step 6.3: Update MessageBusExecutor**

Update `src/picklebot/core/messagebus_executor.py`:

```python
"""Message bus executor for handling platform messages."""

import asyncio
import logging
from typing import Any

from picklebot.core.context import SharedContext
from picklebot.core.agent import Agent
from picklebot.messagebus.base import MessageBus
from picklebot.frontend.base import SilentFrontend

logger = logging.getLogger(__name__)


class MessageBusExecutor:
    """Orchestrates message flow between platforms and agent."""

    def __init__(self, context: SharedContext, buses: list[MessageBus]):
        """
        Initialize MessageBusExecutor.

        Args:
            context: Shared application context
            buses: List of message bus implementations
        """
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Single shared session for all platforms
        agent_def = context.agent_loader.load(context.config.default_agent)
        agent = Agent(agent_def=agent_def, context=context)
        self.session = agent.new_session()

        # Message queue for sequential processing
        # Stores (message, platform, context) - context is platform-specific
        self.message_queue: asyncio.Queue[tuple[str, str, Any]] = asyncio.Queue()
        self.frontend = SilentFrontend()

    async def run(self) -> None:
        """Start message processing loop and all buses."""
        logger.info("MessageBusExecutor started")

        worker_task = asyncio.create_task(self._process_messages())
        bus_tasks = [bus.start(self._enqueue_message) for bus in self.buses]

        try:
            await asyncio.gather(worker_task, *bus_tasks)
        except asyncio.CancelledError:
            logger.info("MessageBusExecutor shutting down...")
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    async def _enqueue_message(self, message: str, platform: str, context: Any) -> None:
        """
        Add incoming message to queue (called by buses).

        Args:
            message: User message content
            platform: Platform identifier
            context: Platform-specific message context
        """
        bus = self.bus_map[platform]

        # Delegate whitelist check to bus
        if not bus.is_allowed(context):
            logger.info(f"Ignored message from non-whitelisted user on {platform}")
            return

        await self.message_queue.put((message, platform, context))
        logger.debug(f"Enqueued message from {platform}")

    async def _process_messages(self) -> None:
        """Worker that processes messages sequentially from queue."""
        while True:
            message, platform, context = await self.message_queue.get()

            logger.info(f"Processing message from {platform}")

            try:
                response = await self.session.chat(message, self.frontend)
                await self.bus_map[platform].reply(content=response, context=context)
                logger.info(f"Sent response to {platform}")
            except Exception as e:
                logger.error(f"Error processing message from {platform}: {e}")
                try:
                    await self.bus_map[platform].reply(
                        content="Sorry, I encountered an error processing your message.",
                        context=context,
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
            finally:
                self.message_queue.task_done()
```

**Step 6.4: Update tests to use new interface**

Update the test methods that use `MockContext`:

```python
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
        """Test that messages are processed from queue."""
        executor, bus = executor_with_mock_bus

        with patch.object(executor.session, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Test response"

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

        with patch.object(executor.session, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("LLM error")

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
        """Test that executor routes messages to correct platforms."""
        _create_test_agent(test_config.agents_path)

        context = SharedContext(test_config)

        bus1 = MockBus("telegram")
        bus2 = MockBus("discord")
        executor = MessageBusExecutor(context, [bus1, bus2])

        with patch.object(executor.session, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Test response"

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
```

**Step 6.5: Run all executor tests**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: PASS

**Step 6.6: Commit**

```bash
git add src/picklebot/core/messagebus_executor.py tests/core/test_messagebus_executor.py
git commit -m "refactor(executor): update to use context-based bus interface"
```

---

## Task 7: Update PostMessageTool

**Files:**
- Modify: `src/picklebot/tools/post_message_tool.py`
- Modify: `tests/tools/test_post_message_tool.py`

**Step 7.1: Update test to use post()**

Update `tests/tools/test_post_message_tool.py`:

```python
class TestPostMessageToolExecution:
    """Tests for post_message tool execution."""

    @pytest.mark.anyio
    async def test_sends_message_to_default_platform(self):
        """Should send message to default_platform using post()."""

        context = _make_context_with_messagebus(enabled=True, default_platform="telegram")

        # Find the telegram bus and mock its post method
        telegram_bus = next(
            (b for b in context.messagebus_buses if b.platform_name == "telegram"), None
        )
        assert telegram_bus is not None

        # Mock post
        original_post = telegram_bus.post
        telegram_bus.post = AsyncMock()

        tool = create_post_message_tool(context)
        assert tool is not None

        result = await tool.execute(content="Hello from agent!")

        telegram_bus.post.assert_called_once_with(content="Hello from agent!", target=None)
        assert "sent" in result.lower() or "success" in result.lower()

        # Restore
        telegram_bus.post = original_post
```

**Step 7.2: Run test, verify it fails**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: FAIL (still using send_message)

**Step 7.3: Update post_message_tool.py**

Update `src/picklebot/tools/post_message_tool.py`:

```python
    async def post_message(content: str) -> str:
        """
        Send a message to the default destination on the default platform.

        Args:
            content: Message content to send

        Returns:
            Success or error message
        """
        try:
            await default_bus.post(content=content)
            return f"Message sent successfully to {default_platform}"
        except Exception as e:
            return f"Failed to send message: {e}"
```

**Step 7.4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: PASS

**Step 7.5: Commit**

```bash
git add src/picklebot/tools/post_message_tool.py tests/tools/test_post_message_tool.py
git commit -m "refactor(post_message): use bus.post() instead of send_message()"
```

---

## Task 8: Run Full Test Suite and Fix Issues

**Step 8.1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: Some tests may fail due to interface changes

**Step 8.2: Fix any remaining issues**

Address any test failures by updating test code or implementation.

**Step 8.3: Run linting and type checking**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 8.4: Final commit if needed**

```bash
git add .
git commit -m "fix: address remaining test and lint issues"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `docs/messagebus-setup.md`
- Modify: `CLAUDE.md`

**Step 9.1: Update config field names in docs**

Replace all references to `default_user_id` with `default_chat_id` in documentation.

**Step 9.2: Update architecture description**

Update `CLAUDE.md` to reflect new interface:

```markdown
**MessageBus** (`messagebus/base.py`): Abstract generic base with platform-specific context.
Key methods: `is_allowed(context)`, `reply(content, context)`, `post(content, target=None)`.
Implementations: `TelegramBus[TelegramContext]`, `DiscordBus[DiscordContext]`.
```

**Step 9.3: Commit**

```bash
git add docs/messagebus-setup.md CLAUDE.md
git commit -m "docs: update messagebus documentation for context refactor"
```

---

## Summary

This plan refactors the MessageBus system to:

1. Use platform-specific context classes (`TelegramContext`, `DiscordContext`)
2. Separate whitelisting (by `user_id`) from replying (by `chat_id`/`channel_id`)
3. Provide clear `is_allowed()`, `reply()`, and `post()` methods
4. Rename config field `default_user_id` → `default_chat_id` for clarity
