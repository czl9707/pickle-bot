# MessageBus Running Task Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `MessageBus.start()` return an `asyncio.Task` that runs until the bus stops, preventing the worker from exiting immediately.

**Architecture:** For DiscordBus, return the `client.start()` task directly. For TelegramBus, create a wrapper task that monitors `updater.running` and waits on a stop event. Both implementations are idempotent - calling `start()` twice returns the same task.

**Tech Stack:** Python, asyncio, pytest, pytest-anyio

---

## Task 1: Write Tests for TelegramBus Running Task

**Files:**
- Modify: `tests/messagebus/test_telegram_bus.py`

**Step 1: Add test for start returning a task**

Add this test class after the existing tests:

```python
class TestTelegramBusRunningTask:
    """Tests for start() returning a running task."""

    @pytest.mark.anyio
    async def test_start_returns_task(self):
        """start() should return an asyncio.Task."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        mock_app = MagicMock()
        mock_app.updater = MagicMock()
        mock_app.updater.running = True
        mock_app.updater.start_polling = AsyncMock()
        mock_app.updater.stop = AsyncMock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.add_handler = MagicMock()

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            import asyncio
            task = await bus.start(dummy_callback)

            assert isinstance(task, asyncio.Task)

            # Clean up
            await bus.stop()

    @pytest.mark.anyio
    async def test_start_returns_same_task_if_called_twice(self):
        """Calling start() twice should return the same task."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        mock_app = MagicMock()
        mock_app.updater = MagicMock()
        mock_app.updater.running = True
        mock_app.updater.start_polling = AsyncMock()
        mock_app.updater.stop = AsyncMock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.add_handler = MagicMock()

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            task1 = await bus.start(dummy_callback)
            task2 = await bus.start(dummy_callback)

            assert task1 is task2

            # Clean up
            await bus.stop()

    @pytest.mark.anyio
    async def test_task_completes_on_stop(self):
        """The running task should complete when stop() is called."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        mock_app = MagicMock()
        mock_app.updater = MagicMock()
        mock_app.updater.running = True
        mock_app.updater.start_polling = AsyncMock()
        mock_app.updater.stop = AsyncMock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.add_handler = MagicMock()

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            task = await bus.start(dummy_callback)

            # Task should not be done yet
            assert not task.done()

            # Stop the bus
            await bus.stop()

            # Task should be done after stop
            assert task.done()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py::TestTelegramBusRunningTask -v`

Expected: FAIL - start() currently returns None

---

## Task 2: Implement TelegramBus Running Task

**Files:**
- Modify: `src/picklebot/messagebus/telegram_bus.py`

**Step 1: Add asyncio import**

Add `asyncio` to the imports at the top:

```python
import asyncio
from dataclasses import dataclass
import logging
from typing import Callable, Awaitable
```

**Step 2: Add new attributes to `__init__`**

Update `__init__` to include new attributes:

```python
    def __init__(self, config: TelegramConfig):
        """
        Initialize TelegramBus.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self.application: Application | None = None
        self._running_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
```

**Step 3: Update `start()` to return a task**

Replace the `start` method (lines 46-92) with:

```python
    async def start(
        self, on_message: Callable[[str, TelegramContext], Awaitable[None]]
    ) -> asyncio.Task | None:
        """Start listening for Telegram messages.

        Returns:
            Task that runs until stop() is called, or None if already started.
        """
        # Idempotent: return existing task if already started
        if self.application is not None:
            logger.debug("TelegramBus already started, returning existing task")
            return self._running_task

        logger.info(f"Message bus enabled with platform: {self.platform_name}")
        self.application = Application.builder().token(self.config.bot_token).build()
        self._stop_event = asyncio.Event()

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming Telegram message."""
            if (
                update.message
                and update.message.text
                and update.effective_chat
                and update.message.from_user
            ):
                # Extract user_id (the person) and chat_id (the conversation)
                user_id = str(update.message.from_user.id)
                chat_id = str(update.effective_chat.id)
                message = update.message.text

                logger.info(
                    f"Received Telegram message from user {user_id} in chat {chat_id}"
                )

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

        # Create the running task that monitors for stop
        async def run_until_stopped():
            """Run until stop() is called or updater stops unexpectedly."""
            while self.application and self.application.updater:
                if self.application.updater.running:
                    if self._stop_event and self._stop_event.is_set():
                        return  # Graceful stop
                    await asyncio.sleep(0.5)
                else:
                    # Updater stopped without us calling stop()
                    if self._stop_event and not self._stop_event.is_set():
                        raise RuntimeError("Telegram updater stopped unexpectedly")
                    return

        self._running_task = asyncio.create_task(run_until_stopped())
        return self._running_task
```

**Step 4: Update `stop()` to signal the task**

Replace the `stop` method (lines 126-138) with:

```python
    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        # Idempotent: skip if not running
        if self.application is None:
            logger.debug("TelegramBus not running, skipping stop")
            return

        # Signal the running task to stop
        if self._stop_event:
            self._stop_event.set()

        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

        # Wait for running task to complete
        if self._running_task and not self._running_task.done():
            try:
                await asyncio.wait_for(self._running_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Running task did not complete in time")
            except Exception:
                pass  # Task may have already failed

        self.application = None
        self._running_task = None
        self._stop_event = None
        logger.info("TelegramBus stopped")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/picklebot/messagebus/telegram_bus.py tests/messagebus/test_telegram_bus.py
git commit -m "feat: make TelegramBus.start() return a running task"
```

---

## Task 3: Write Tests for DiscordBus Running Task

**Files:**
- Modify: `tests/messagebus/test_discord_bus.py`

**Step 1: Add test for start returning a task**

Add this test class after the existing tests:

```python
class TestDiscordBusRunningTask:
    """Tests for start() returning a running task."""

    @pytest.mark.anyio
    async def test_start_returns_task(self):
        """start() should return an asyncio.Task."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            import asyncio
            task = await bus.start(dummy_callback)

            assert isinstance(task, asyncio.Task)

            # Clean up
            await bus.stop()

    @pytest.mark.anyio
    async def test_start_returns_same_task_if_called_twice(self):
        """Calling start() twice should return the same task."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            task1 = await bus.start(dummy_callback)
            task2 = await bus.start(dummy_callback)

            assert task1 is task2

            # Clean up
            await bus.stop()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/messagebus/test_discord_bus.py::TestDiscordBusRunningTask -v`

Expected: FAIL - start() currently returns None

---

## Task 4: Implement DiscordBus Running Task

**Files:**
- Modify: `src/picklebot/messagebus/discord_bus.py`

**Step 1: Add new attribute to `__init__`**

Update `__init__` to include new attribute:

```python
    def __init__(self, config: DiscordConfig):
        """
        Initialize DiscordBus.

        Args:
            config: Discord configuration
        """
        self.config = config
        self.client: discord.Client | None = None
        self._running_task: asyncio.Task | None = None
```

**Step 2: Update `start()` to return a task**

Replace the `start` method (lines 38-96) with:

```python
    async def start(
        self, on_message: Callable[[str, DiscordContext], Awaitable[None]]
    ) -> asyncio.Task | None:
        """Start listening for Discord messages.

        Returns:
            Task that runs until stop() is called, or None if already started.
        """
        # Idempotent: return existing task if already started
        if self.client is not None:
            logger.debug("DiscordBus already started, returning existing task")
            return self._running_task

        logger.info(f"Message bus enabled with platform: {self.platform_name}")

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def _on_discord_message(message: discord.Message) -> None:
            """Handle incoming Discord message."""
            # Ignore bot's own messages
            if self.client and message.author == self.client.user:
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

            logger.info(
                f"Received Discord message from user {user_id} in channel {channel_id}"
            )

            ctx = DiscordContext(user_id=user_id, channel_id=channel_id)

            try:
                await on_message(content, ctx)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Start the bot and store the task
        self._running_task = asyncio.create_task(self.client.start(self.config.bot_token))

        # Wait a moment for client to initialize
        await asyncio.sleep(0.5)

        logger.info("DiscordBus started")
        return self._running_task
```

**Step 3: Update `stop()` to wait for task**

Replace the `stop` method (lines 142-151) with:

```python
    async def stop(self) -> None:
        """Stop Discord bot and cleanup."""
        # Idempotent: skip if not running
        if self.client is None:
            logger.debug("DiscordBus not running, skipping stop")
            return

        await self.client.close()

        # Wait for running task to complete
        if self._running_task and not self._running_task.done():
            try:
                await asyncio.wait_for(self._running_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Running task did not complete in time")
            except Exception:
                pass  # Task may have already failed

        self.client = None
        self._running_task = None
        logger.info("DiscordBus stopped")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/messagebus/discord_bus.py tests/messagebus/test_discord_bus.py
git commit -m "feat: make DiscordBus.start() return a running task"
```

---

## Task 5: Update Base Class Return Type

**Files:**
- Modify: `src/picklebot/messagebus/base.py`

**Step 1: Update `start()` return type**

Update the `start` method signature (line 30):

```python
    @abstractmethod
    async def start(self, on_message: Callable[[str, T], Awaitable[None]]) -> asyncio.Task | None:
        """
        Start listening for messages.

        Args:
            on_message: Callback async function(message: str, context: T)

        Returns:
            Task that runs until stop() is called, or None if already started.
        """
        pass
```

**Step 2: Add asyncio import**

Add `asyncio` to imports at the top:

```python
import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Generic, TypeVar, Any
```

**Step 3: Run all messagebus tests**

Run: `uv run pytest tests/messagebus/ -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/picklebot/messagebus/base.py
git commit -m "refactor: update MessageBus.start() return type to Task | None"
```

---

## Task 6: Final Verification

**Files:**
- Verify: All messagebus tests pass

**Step 1: Run all messagebus tests**

Run: `uv run pytest tests/messagebus/ -v`

Expected: All tests PASS

**Step 2: Run full test suite**

Run: `uv run pytest`

Expected: All tests PASS

**Step 3: Review final state**

Run: `git status`

Expected: All changes committed

---

## Success Criteria

- [ ] `TelegramBus.start()` returns an `asyncio.Task`
- [ ] `DiscordBus.start()` returns an `asyncio.Task`
- [ ] Tasks complete when `stop()` is called
- [ ] Calling `start()` twice returns the same task (idempotent)
- [ ] All existing tests still pass
- [ ] New tests cover running task behavior
