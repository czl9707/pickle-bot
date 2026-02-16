# Message Bus Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time messaging platform support (Telegram, Discord) to pickle-bot with event-driven architecture.

**Architecture:** Refactor Frontend to pure display, add MessageBus abstraction layer, implement queue-based MessageBusExecutor running alongside CronExecutor in server process.

**Tech Stack:** python-telegram-bot, discord.py, asyncio.Queue

---

## Task 1: Refactor Frontend Interface

**Files:**
- Modify: `src/picklebot/frontend/base.py:16-17`
- Modify: `src/picklebot/frontend/console.py:38-40`
- Modify: `src/picklebot/cli/chat.py:26-28`

**Step 1: Update Frontend abstract interface**

Remove `get_user_input()` method from Frontend base class:

```python
# src/picklebot/frontend/base.py
"""Abstract base class for frontend implementations."""

from abc import ABC, abstractmethod
import contextlib
from typing import Iterator


class Frontend(ABC):
    """Abstract interface for frontend implementations."""

    @abstractmethod
    def show_welcome(self) -> None:
        """Display welcome message."""
        pass

    @abstractmethod
    def show_message(self, content: str) -> None:
        """Display a message (user or agent)."""
        pass

    @abstractmethod
    def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        pass

    @abstractmethod
    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield


class SilentFrontend(Frontend):
    """No-op frontend for unattended execution (e.g., cron jobs)."""

    def show_welcome(self) -> None:
        pass

    def show_message(self, content: str) -> None:
        pass

    def show_system_message(self, content: str) -> None:
        pass

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        yield
```

**Step 2: Update ConsoleFrontend**

Replace `show_agent_response()` with `show_message()`, remove `get_user_input()`:

```python
# src/picklebot/frontend/console.py
"""Console frontend implementation using Rich."""

import contextlib
from typing import Iterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent_loader import AgentDef
from .base import Frontend


class ConsoleFrontend(Frontend):
    """Console-based frontend using Rich for formatting."""

    def __init__(self, agent_def: AgentDef):
        """
        Initialize console frontend.

        Args:
            agent_def: Agent definition
        """
        self.agent_def = agent_def
        self.console = Console()

    def show_welcome(self) -> None:
        """Display welcome message panel."""
        self.console.print(
            Panel(
                Text(f"Welcome to {self.agent_def.name}!", style="bold cyan"),
                title="🐈 Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    def show_message(self, content: str) -> None:
        """Display a message."""
        self.console.print(content)

    def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        self.console.print(content)

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield
```

**Step 3: Update ChatLoop to handle input directly**

```python
# src/picklebot/cli/chat.py
"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, SharedContext
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        self.context = SharedContext(config=config)

        self.agent_def = self.context.agent_loader.load(self.agent_id)
        self.frontend = ConsoleFrontend(self.agent_def)
        self.agent = Agent(agent_def=self.agent_def, context=self.context)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        session = self.agent.new_session()
        self.frontend.show_welcome()

        while True:
            try:
                # Get input directly (no longer in Frontend)
                user_input = self.frontend.console.input("[bold green]You:[/bold green] ")

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Show user message
                self.frontend.show_message(f"[bold green]You:[/bold green] {user_input}")

                # Get response
                response = await session.chat(user_input, self.frontend)

                # Show agent response
                self.frontend.show_message(f"[bold cyan]{self.agent_def.name}:[/bold cyan] {response}")

            except KeyboardInterrupt:
                self.frontend.show_system_message(
                    "\n[yellow]Session interrupted.[/yellow]"
                )
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
```

**Step 4: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests pass (we didn't change behavior, just refactored)

**Step 5: Commit refactored Frontend**

```bash
git add src/picklebot/frontend/base.py src/picklebot/frontend/console.py src/picklebot/cli/chat.py
git commit -m "refactor: Frontend to pure display interface

- Remove get_user_input() from Frontend interface
- Rename show_agent_response() to show_message()
- Move input handling to ChatLoop
- Update ConsoleFrontend implementation"
```

---

## Task 2: Create MessageBus Abstraction

**Files:**
- Create: `src/picklebot/messagebus/__init__.py`
- Create: `src/picklebot/messagebus/base.py`

**Step 1: Write test for MessageBus interface**

```python
# tests/messagebus/test_base.py
"""Tests for MessageBus abstract interface."""

import pytest
from picklebot.messagebus.base import MessageBus


class MockBus(MessageBus):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, user_id: str, content: str) -> None:
        pass

    async def stop(self) -> None:
        pass


def test_messagebus_has_platform_name():
    """Test that MessageBus has platform_name property."""
    bus = MockBus()
    assert bus.platform_name == "mock"


@pytest.mark.asyncio
async def test_messagebus_send_message_interface():
    """Test that send_message can be called."""
    bus = MockBus()
    await bus.send_message("user123", "test message")
    # Should not raise
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_base.py -v`
Expected: FAIL with "No module named 'picklebot.messagebus'"

**Step 3: Create messagebus module structure**

```python
# src/picklebot/messagebus/__init__.py
"""Message bus implementations for different platforms."""

from picklebot.messagebus.base import MessageBus

__all__ = ["MessageBus"]
```

```python
# src/picklebot/messagebus/base.py
"""Abstract base class for message bus implementations."""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class MessageBus(ABC):
    """Abstract base for messaging platforms."""

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
    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for messages.

        Args:
            on_message: Callback async function(message: str, platform: str, user_id: str)
        """
        pass

    @abstractmethod
    async def send_message(self, user_id: str, content: str) -> None:
        """
        Send message to specific user on this platform.

        Args:
            user_id: Platform-specific user identifier
            content: Message content to send
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_base.py -v`
Expected: PASS

**Step 5: Commit MessageBus abstraction**

```bash
git add src/picklebot/messagebus/ tests/messagebus/
git commit -m "feat: add MessageBus abstract interface

- Create messagebus module
- Define MessageBus abstract base class
- Add test for interface contract"
```

---

## Task 3: Add MessageBus Configuration

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `pyproject.toml`

**Step 1: Add dependencies to pyproject.toml**

```toml
# pyproject.toml
[project]
dependencies = [
  # ... existing
  "python-telegram-bot>=20.0",
  "discord.py>=2.0",
]
```

**Step 2: Add MessageBus config models**

```python
# src/picklebot/utils/config.py
# Add to imports
from pydantic import model_validator

# Add new model classes
class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str


class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None


class MessageBusConfig(BaseModel):
    """Message bus configuration."""

    enabled: bool = False
    default_platform: str | None = None
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None

    @model_validator(mode="after")
    def validate_default_platform(self) -> "MessageBusConfig":
        """Validate default_platform is configured when enabled."""
        if self.enabled:
            # default_platform is required when enabled
            if not self.default_platform:
                raise ValueError("default_platform is required when messagebus is enabled")

            # Verify default_platform has valid config
            if self.default_platform == "telegram" and not self.telegram:
                raise ValueError("default_platform is 'telegram' but telegram config is missing")
            if self.default_platform == "discord" and not self.discord:
                raise ValueError("default_platform is 'discord' but discord config is missing")
            if self.default_platform not in ["telegram", "discord"]:
                raise ValueError(f"Invalid default_platform: {self.default_platform}")

        return self


# Update Config class
class Config(BaseModel):
    """Application configuration."""

    # ... existing fields
    messagebus: MessageBusConfig = MessageBusConfig()
```

**Step 3: Write test for config validation**

```python
# tests/utils/test_config_validation.py
"""Tests for config validation."""

import pytest
from picklebot.utils.config import Config, MessageBusConfig, TelegramConfig


def test_messagebus_disabled_by_default():
    """Test that messagebus is disabled by default."""
    config = Config()
    assert not config.messagebus.enabled


def test_messagebus_enabled_requires_default_platform():
    """Test that enabled messagebus requires default_platform."""
    with pytest.raises(ValueError, match="default_platform is required"):
        MessageBusConfig(enabled=True)


def test_messagebus_validates_platform_config():
    """Test that default_platform must have valid config."""
    with pytest.raises(ValueError, match="telegram config is missing"):
        MessageBusConfig(enabled=True, default_platform="telegram")


def test_messagebus_valid_config():
    """Test valid messagebus configuration."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(bot_token="test_token")
    )
    assert config.enabled
    assert config.default_platform == "telegram"
```

**Step 4: Run tests**

Run: `uv run pytest tests/utils/test_config_validation.py -v`
Expected: All tests pass

**Step 5: Commit configuration**

```bash
git add pyproject.toml src/picklebot/utils/config.py tests/utils/test_config_validation.py
git commit -m "feat: add MessageBus configuration

- Add TelegramConfig and DiscordConfig models
- Add MessageBusConfig with validation
- Require default_platform when enabled
- Add config validation tests
- Add python-telegram-bot and discord.py dependencies"
```

---

## Task 4: Create MessageBusExecutor

**Files:**
- Create: `src/picklebot/core/messagebus_executor.py`

**Step 1: Write test for MessageBusExecutor**

```python
# tests/core/test_messagebus_executor.py
"""Tests for MessageBusExecutor."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock

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
def mock_context():
    """Create mock context."""
    from picklebot.utils.config import Config
    from picklebot.core.context import SharedContext

    config = Config()
    return SharedContext(config)


@pytest.mark.asyncio
async def test_messagebus_executor_enqueue_message(mock_context):
    """Test that messages are enqueued."""
    bus = MockBus("mock")
    executor = MessageBusExecutor(mock_context, [bus])

    await executor._enqueue_message("Hello", "mock", "user123")

    assert executor.message_queue.qsize() == 1


@pytest.mark.asyncio
async def test_messagebus_executor_processes_queue(mock_context):
    """Test that messages are processed from queue."""
    bus = MockBus("mock")
    executor = MessageBusExecutor(mock_context, [bus])

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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: FAIL with "No module named 'picklebot.core.messagebus_executor'"

**Step 3: Create MessageBusExecutor**

```python
# src/picklebot/core/messagebus_executor.py
"""Message bus executor for handling platform messages."""

import asyncio
import logging
from typing import Callable, Awaitable

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
        self.context = context
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Single shared session for all platforms
        self.agent_def = context.agent_loader.load(context.config.default_agent)
        self.agent = Agent(agent_def, context)
        self.session = agent.new_session()

        # Message queue for sequential processing
        self.message_queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
        self.frontend = SilentFrontend()

    async def run(self) -> None:
        """Start message processing loop and all buses."""
        logger.info("MessageBusExecutor started")

        # Start worker task to process messages
        worker_task = asyncio.create_task(self._process_messages())

        # Start all message buses
        bus_tasks = [bus.start(self._enqueue_message) for bus in self.buses]

        try:
            await asyncio.gather(worker_task, *bus_tasks)
        except asyncio.CancelledError:
            logger.info("MessageBusExecutor shutting down...")
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

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
        await self.message_queue.put((message, platform, user_id))
        logger.debug(f"Enqueued message from {platform}/{user_id}")

    async def _process_messages(self) -> None:
        """Worker that processes messages sequentially from queue."""
        while True:
            message, platform, user_id = await self.message_queue.get()

            logger.info(f"Processing message from {platform}/{user_id}")

            try:
                response = await self.session.chat(message, self.frontend)
                await self.bus_map[platform].send_message(user_id, response)
                logger.info(f"Sent response to {platform}/{user_id}")
            except Exception as e:
                logger.error(f"Error processing message from {platform}: {e}")
                try:
                    await self.bus_map[platform].send_message(
                        user_id,
                        "Sorry, I encountered an error processing your message.",
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
            finally:
                self.message_queue.task_done()
```

**Step 4: Run tests**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: All tests pass

**Step 5: Commit MessageBusExecutor**

```bash
git add src/picklebot/core/messagebus_executor.py tests/core/test_messagebus_executor.py
git commit -m "feat: add MessageBusExecutor with queue-based processing

- Create MessageBusExecutor to orchestrate message flow
- Use asyncio.Queue for sequential message processing
- Single shared AgentSession across all platforms
- Error handling with user-friendly messages
- Add tests for queue processing"
```

---

## Task 5: Implement TelegramBus

**Files:**
- Create: `src/picklebot/messagebus/telegram_bus.py`

**Step 1: Write test for TelegramBus**

```python
# tests/messagebus/test_telegram_bus.py
"""Tests for TelegramBus."""

import pytest
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.utils.config import TelegramConfig


def test_telegram_bus_platform_name():
    """Test that TelegramBus has correct platform name."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)
    assert bus.platform_name == "telegram"


@pytest.mark.asyncio
async def test_telegram_bus_start_stop():
    """Test that TelegramBus can start and stop."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    # Should not raise
    await bus.start(lambda msg, plat, uid: None)
    await bus.stop()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`
Expected: FAIL with "No module named 'picklebot.messagebus.telegram_bus'"

**Step 3: Implement TelegramBus**

```python
# src/picklebot/messagebus/telegram_bus.py
"""Telegram message bus implementation."""

import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramBus(MessageBus):
    """Telegram platform implementation using python-telegram-bot."""

    def __init__(self, config: TelegramConfig):
        """
        Initialize TelegramBus.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self.application: Application | None = None

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "telegram"

    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for Telegram messages.

        Args:
            on_message: Callback for incoming messages
        """
        self.application = Application.builder().token(self.config.bot_token).build()

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming Telegram message."""
            if update.message and update.message.text:
                user_id = str(update.effective_chat.id)
                message = update.message.text

                logger.info(f"Received Telegram message from {user_id}")

                try:
                    await on_message(message, self.platform_name, user_id)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

        # Add message handler
        handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        self.application.add_handler(handler)

        # Start the bot
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("TelegramBus started")

    async def send_message(self, user_id: str, content: str) -> None:
        """
        Send message to Telegram user.

        Args:
            user_id: Telegram chat ID
            content: Message content
        """
        if not self.application:
            raise RuntimeError("TelegramBus not started")

        try:
            await self.application.bot.send_message(
                chat_id=int(user_id), text=content
            )
            logger.debug(f"Sent Telegram message to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            raise

    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        if self.application:
            if self.application.updater.running:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("TelegramBus stopped")
```

**Step 4: Run tests**

Run: `uv run pytest tests/messagebus/test_telegram_bus.py -v`
Expected: All tests pass

**Step 5: Commit TelegramBus**

```bash
git add src/picklebot/messagebus/telegram_bus.py tests/messagebus/test_telegram_bus.py
git commit -m "feat: implement TelegramBus

- Use python-telegram-bot with polling mode
- Handle incoming text messages
- Send responses to specific chat IDs
- Add basic tests"
```

---

## Task 6: Implement DiscordBus

**Files:**
- Create: `src/picklebot/messagebus/discord_bus.py`

**Step 1: Write test for DiscordBus**

```python
# tests/messagebus/test_discord_bus.py
"""Tests for DiscordBus."""

import pytest
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import DiscordConfig


def test_discord_bus_platform_name():
    """Test that DiscordBus has correct platform name."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)
    assert bus.platform_name == "discord"


@pytest.mark.asyncio
async def test_discord_bus_start_stop():
    """Test that DiscordBus can start and stop."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)

    # Should not raise
    await bus.start(lambda msg, plat, uid: None)
    # Note: Discord bot needs event loop to fully start, so we just test it doesn't crash
    await bus.stop()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`
Expected: FAIL with "No module named 'picklebot.messagebus.discord_bus'"

**Step 3: Implement DiscordBus**

```python
# src/picklebot/messagebus/discord_bus.py
"""Discord message bus implementation."""

import asyncio
import logging
from typing import Callable, Awaitable

import discord

from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import DiscordConfig

logger = logging.getLogger(__name__)


class DiscordBus(MessageBus):
    """Discord platform implementation using discord.py."""

    def __init__(self, config: DiscordConfig):
        """
        Initialize DiscordBus.

        Args:
            config: Discord configuration
        """
        self.config = config
        self.client: discord.Client | None = None
        self._on_message: Callable[[str, str, str], Awaitable[None]] | None = None

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "discord"

    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for Discord messages.

        Args:
            on_message: Callback for incoming messages
        """
        self._on_message = on_message

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_message(message: discord.Message):
            """Handle incoming Discord message."""
            # Ignore bot's own messages
            if message.author == self.client.user:
                return

            # Check channel restriction
            if self.config.channel_id and str(message.channel.id) != self.config.channel_id:
                return

            # Only handle text messages
            if not message.content:
                return

            user_id = str(message.channel.id)
            content = message.content

            logger.info(f"Received Discord message from {user_id}")

            try:
                await self._on_message(content, self.platform_name, user_id)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Start the bot in background
        asyncio.create_task(self.client.start(self.config.bot_token))

        # Wait a moment for client to initialize
        await asyncio.sleep(0.5)

        logger.info("DiscordBus started")

    async def send_message(self, user_id: str, content: str) -> None:
        """
        Send message to Discord channel.

        Args:
            user_id: Discord channel ID
            content: Message content
        """
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        try:
            channel = self.client.get_channel(int(user_id))
            if not channel:
                raise ValueError(f"Channel {user_id} not found")

            await channel.send(content)
            logger.debug(f"Sent Discord message to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            raise

    async def stop(self) -> None:
        """Stop Discord bot and cleanup."""
        if self.client:
            await self.client.close()
            logger.info("DiscordBus stopped")
```

**Step 4: Run tests**

Run: `uv run pytest tests/messagebus/test_discord_bus.py -v`
Expected: All tests pass

**Step 5: Commit DiscordBus**

```bash
git add src/picklebot/messagebus/discord_bus.py tests/messagebus/test_discord_bus.py
git commit -m "feat: implement DiscordBus

- Use discord.py with message content intents
- Support DMs or specific channel restriction
- Handle incoming text messages
- Send responses to channels
- Add basic tests"
```

---

## Task 7: Update Server Command

**Files:**
- Modify: `src/picklebot/cli/server.py`

**Step 1: Write test for updated server**

```python
# tests/cli/test_server_integration.py
"""Tests for server integration with message bus."""

import pytest
from picklebot.utils.config import Config, MessageBusConfig, TelegramConfig
from picklebot.messagebus.telegram_bus import TelegramBus


def test_create_buses_from_config():
    """Test creating buses from config."""
    from picklebot.cli.server import create_buses_from_config

    config = Config(
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(bot_token="test_token")
        )
    )

    buses = create_buses_from_config(config)

    assert len(buses) == 1
    assert buses[0].platform_name == "telegram"


def test_create_buses_disabled():
    """Test that disabled buses are not created."""
    from picklebot.cli.server import create_buses_from_config

    config = Config(messagebus=MessageBusConfig(enabled=False))

    buses = create_buses_from_config(config)

    assert len(buses) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_server_integration.py -v`
Expected: FAIL with "cannot import name 'create_buses_from_config'"

**Step 3: Update server.py**

```python
# src/picklebot/cli/server.py
"""Server CLI command for cron and message bus execution."""

import asyncio
import logging

import typer

from picklebot.core.context import SharedContext
from picklebot.core.cron_executor import CronExecutor
from picklebot.core.messagebus_executor import MessageBusExecutor
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import Config

logger = logging.getLogger(__name__)


def create_buses_from_config(config: Config) -> list:
    """
    Create message bus instances from configuration.

    Args:
        config: Application configuration

    Returns:
        List of MessageBus instances
    """
    buses = []

    if config.messagebus.telegram and config.messagebus.telegram.enabled:
        buses.append(TelegramBus(config.messagebus.telegram))

    if config.messagebus.discord and config.messagebus.discord.enabled:
        buses.append(DiscordBus(config.messagebus.discord))

    return buses


def server_command(ctx: typer.Context) -> None:
    """Start the 24/7 server for cron job and message bus execution."""
    config = ctx.obj.get("config")
    context = SharedContext(config)

    typer.echo("Starting pickle-bot server...")
    typer.echo(f"Crons path: {config.crons_path}")

    if config.messagebus.enabled:
        typer.echo(f"Message bus: enabled (default platform: {config.messagebus.default_platform})")
    else:
        typer.echo("Message bus: disabled")

    typer.echo("Press Ctrl+C to stop")

    try:
        asyncio.run(_run_server(context, config))
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")


async def _run_server(context: SharedContext, config: Config) -> None:
    """
    Run server with all executors.

    Args:
        context: Shared application context
        config: Application configuration
    """
    tasks = []

    # Cron executor (always runs)
    cron_executor = CronExecutor(context)
    tasks.append(cron_executor.run())

    # Message bus executor (if enabled)
    if config.messagebus.enabled:
        buses = create_buses_from_config(config)
        if buses:
            messagebus_executor = MessageBusExecutor(context, buses)
            tasks.append(messagebus_executor.run())
        else:
            logger.warning("Message bus enabled but no platforms configured")

    await asyncio.gather(*tasks, return_exceptions=False)
```

**Step 4: Run tests**

Run: `uv run pytest tests/cli/test_server_integration.py -v`
Expected: All tests pass

**Step 5: Commit server updates**

```bash
git add src/picklebot/cli/server.py tests/cli/test_server_integration.py
git commit -m "feat: integrate MessageBusExecutor into server

- Add create_buses_from_config helper
- Run MessageBusExecutor alongside CronExecutor
- Add message bus status to startup message
- Add tests for bus creation logic"
```

---

## Task 8: Update MessageBus Exports

**Files:**
- Modify: `src/picklebot/messagebus/__init__.py`

**Step 1: Update module exports**

```python
# src/picklebot/messagebus/__init__.py
"""Message bus implementations for different platforms."""

from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus

__all__ = ["MessageBus", "TelegramBus", "DiscordBus"]
```

**Step 2: Verify imports work**

Run: `uv run python -c "from picklebot.messagebus import TelegramBus, DiscordBus; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/picklebot/messagebus/__init__.py
git commit -m "chore: export TelegramBus and DiscordBus from messagebus module"
```

---

## Task 9: Add Integration Documentation

**Files:**
- Create: `docs/messagebus-setup.md`

**Step 1: Create setup guide**

```markdown
# Message Bus Setup Guide

## Telegram Setup

1. Create a Telegram bot:
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. Add to config:
   ```yaml
   # ~/.pickle-bot/config.user.yaml
   messagebus:
     enabled: true
     default_platform: "telegram"
     telegram:
       bot_token: "YOUR_BOT_TOKEN"
   ```

3. Start server:
   ```bash
   uv run picklebot server
   ```

4. Test:
   - Open Telegram
   - Find your bot
   - Send a message
   - Verify response

## Discord Setup

1. Create a Discord bot:
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the token
   - Enable "Message Content Intent" under "Privileged Gateway Intents"

2. Invite bot to server:
   - Go to "OAuth2" > "URL Generator"
   - Select "bot" scope
   - Select permissions: "Send Messages", "Read Message History"
   - Copy and open the URL

3. Add to config:
   ```yaml
   # ~/.pickle-bot/config.user.yaml
   messagebus:
     enabled: true
     default_platform: "discord"
     discord:
       bot_token: "YOUR_BOT_TOKEN"
       channel_id: "CHANNEL_ID"  # Optional: restrict to specific channel
   ```

4. Start server and test

## Running Both Platforms

```yaml
messagebus:
  enabled: true
  default_platform: "telegram"  # Cron responses go here
  telegram:
    bot_token: "TELEGRAM_TOKEN"
  discord:
    bot_token: "DISCORD_TOKEN"
```

Both platforms will send messages to the same shared session.
```

**Step 2: Commit docs**

```bash
git add docs/messagebus-setup.md
git commit -m "docs: add message bus setup guide for Telegram and Discord"
```

---

## Task 10: Manual Testing

**No code changes - just verification**

**Test Checklist:**

1. **Configuration Validation:**
   - [ ] Try enabling messagebus without default_platform → verify error
   - [ ] Try setting default_platform to "telegram" without telegram config → verify error
   - [ ] Valid config loads successfully

2. **Telegram:**
   - [ ] Start server with Telegram config
   - [ ] Send message from Telegram
   - [ ] Verify response arrives on Telegram
   - [ ] Send multiple messages rapidly
   - [ ] Verify queue processes them sequentially

3. **Discord:**
   - [ ] Start server with Discord config
   - [ ] Send DM to bot
   - [ ] Verify response arrives on Discord

4. **Both Platforms:**
   - [ ] Enable both Telegram and Discord
   - [ ] Send from Telegram, verify response on Telegram
   - [ ] Send from Discord, verify response on Discord
   - [ ] Test shared session (ask "what did I just say?" from other platform)

5. **Cron Integration:**
   - [ ] Create test cron job
   - [ ] Verify output goes to default_platform

6. **Error Handling:**
   - [ ] Send invalid message (if possible)
   - [ ] Verify error message sent back
   - [ ] Verify server doesn't crash

7. **Shutdown:**
   - [ ] Ctrl+C to stop server
   - [ ] Verify graceful shutdown (no errors)

---

## Completion Checklist

- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy .`
- [ ] Lint passes: `uv run ruff check .`
- [ ] Code formatted: `uv run black .`
- [ ] Manual testing complete (see Task 10)
- [ ] Documentation updated

---

## Implementation Summary

This plan implements the message bus feature with:

1. **Refactored Frontend** - Pure display interface, input handling moved to ChatLoop
2. **MessageBus Abstraction** - Platform-agnostic interface for messaging
3. **Platform Implementations** - Telegram and Discord with real API integration
4. **Queue-Based Processing** - asyncio.Queue for sequential message handling
5. **Configuration** - Validated config with required default_platform
6. **Server Integration** - MessageBusExecutor runs alongside CronExecutor
7. **Shared Session** - All platforms use single AgentSession with sliding window
8. **Error Handling** - Graceful error messages without crashing server

The design maintains the existing architecture patterns while adding event-driven messaging capabilities.
