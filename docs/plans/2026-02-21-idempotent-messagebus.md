# Idempotent MessageBus Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `start()` and `stop()` methods idempotent in TelegramBus and DiscordBus.

**Architecture:** Use existing `application`/`client` attributes as state indicators. Add early returns when already in target state. Reset to `None` after stop to allow restart.

**Tech Stack:** Python, pytest, pytest-anyio, unittest.mock

---

## Task 1: Write Tests for Idempotent TelegramBus

**Files:**
- Modify: `tests/messagebus/test_telegram_bus.py`

**Step 1: Add test for idempotent start**

Add this test class after the existing tests:

```python
class TestTelegramBusIdempotentStartStop:
    """Tests for idempotent start/stop behavior."""

    @pytest.mark.anyio
    async def test_start_is_idempotent(self):
        """Calling start twice should be safe - second call is no-op."""
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

            await bus.start(dummy_callback)
            await bus.start(dummy_callback)  # Second call should be no-op

            # Should only initialize once
            mock_app.initialize.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
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

            await bus.start(dummy_callback)
            await bus.stop()
            await bus.stop()  # Second call should be no-op

            # Should only stop once
            mock_app.stop.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_start_is_safe(self):
        """Calling stop without start should be safe - no-op."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        # Should not raise
        await bus.stop()

    @pytest.mark.anyio
    async def test_can_restart_after_stop(self):
        """Should be able to start again after stop."""
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

            # First cycle
            await bus.start(dummy_callback)
            await bus.stop()

            # Reset mock counts
            mock_app.initialize.reset_mock()

            # Second cycle should work
            await bus.start(dummy_callback)
            mock_app.initialize.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py::TestTelegramBusIdempotentStartStop -v`

Expected: FAIL - start/stop not yet idempotent

---

## Task 2: Implement Idempotent TelegramBus

**Files:**
- Modify: `src/picklebot/messagebus/telegram_bus.py:46-87` (start method)
- Modify: `src/picklebot/messagebus/telegram_bus.py:121-128` (stop method)

**Step 1: Update start method to be idempotent**

Replace the `start` method (lines 46-87) with:

```python
    async def start(
        self, on_message: Callable[[str, TelegramContext], Awaitable[None]]
    ) -> None:
        """Start listening for Telegram messages."""
        # Idempotent: skip if already started
        if self.application is not None:
            logger.debug("TelegramBus already started, skipping")
            return

        logger.info(f"Message bus enabled with platform: {self.platform_name}")
        self.application = Application.builder().token(self.config.bot_token).build()

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
```

**Step 2: Update stop method to be idempotent**

Replace the `stop` method (lines 121-128) with:

```python
    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        # Idempotent: skip if not running
        if self.application is None:
            logger.debug("TelegramBus not running, skipping stop")
            return

        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.application = None  # Reset to allow restart
        logger.info("TelegramBus stopped")
```

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/picklebot/messagebus/telegram_bus.py tests/messagebus/test_telegram_bus.py
git commit -m "feat: make TelegramBus start/stop idempotent"
```

---

## Task 3: Write Tests for Idempotent DiscordBus

**Files:**
- Modify: `tests/messagebus/test_discord_bus.py`

**Step 1: Add test for idempotent start/stop**

Add this test class after the existing tests:

```python
class TestDiscordBusIdempotentStartStop:
    """Tests for idempotent start/stop behavior."""

    @pytest.mark.anyio
    async def test_start_is_idempotent(self):
        """Calling start twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            await bus.start(dummy_callback)
            await bus.start(dummy_callback)  # Second call should be no-op

            # Should only start once (the task is created once)
            mock_client.start.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            await bus.start(dummy_callback)
            await bus.stop()
            await bus.stop()  # Second call should be no-op

            # Should only close once
            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_start_is_safe(self):
        """Calling stop without start should be safe - no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        # Should not raise
        await bus.stop()

    @pytest.mark.anyio
    async def test_can_restart_after_stop(self):
        """Should be able to start again after stop."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            # First cycle
            await bus.start(dummy_callback)
            await bus.stop()

            # Reset mock counts
            mock_client.start.reset_mock()

            # Second cycle should work
            await bus.start(dummy_callback)
            mock_client.start.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/messagebus/test_discord_bus.py::TestDiscordBusIdempotentStartStop -v`

Expected: FAIL - start/stop not yet idempotent

---

## Task 4: Implement Idempotent DiscordBus

**Files:**
- Modify: `src/picklebot/messagebus/discord_bus.py:38-91` (start method)
- Modify: `src/picklebot/messagebus/discord_bus.py:137-141` (stop method)

**Step 1: Update start method to be idempotent**

Replace the `start` method (lines 38-91) with:

```python
    async def start(
        self, on_message: Callable[[str, DiscordContext], Awaitable[None]]
    ) -> None:
        """Start listening for Discord messages."""
        # Idempotent: skip if already started
        if self.client is not None:
            logger.debug("DiscordBus already started, skipping")
            return

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

        # Start the bot in background
        asyncio.create_task(self.client.start(self.config.bot_token))

        # Wait a moment for client to initialize
        await asyncio.sleep(0.5)

        logger.info("DiscordBus started")
```

**Step 2: Update stop method to be idempotent**

Replace the `stop` method (lines 137-141) with:

```python
    async def stop(self) -> None:
        """Stop Discord bot and cleanup."""
        # Idempotent: skip if not running
        if self.client is None:
            logger.debug("DiscordBus not running, skipping stop")
            return

        await self.client.close()
        self.client = None  # Reset to allow restart
        logger.info("DiscordBus stopped")
```

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/picklebot/messagebus/discord_bus.py tests/messagebus/test_discord_bus.py
git commit -m "feat: make DiscordBus start/stop idempotent"
```

---

## Task 5: Final Verification

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

- [ ] TelegramBus.start() is idempotent (safe to call multiple times)
- [ ] TelegramBus.stop() is idempotent (safe to call multiple times)
- [ ] DiscordBus.start() is idempotent (safe to call multiple times)
- [ ] DiscordBus.stop() is idempotent (safe to call multiple times)
- [ ] Both buses can be restarted after stop
- [ ] All existing tests still pass
- [ ] New tests cover idempotent behavior
