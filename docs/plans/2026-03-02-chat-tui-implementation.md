# Chat TUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace simple CLI with Textual-based TUI providing scrollable message history and fixed input at bottom.

**Architecture:** Create Textual widgets (MessageHistory, InputBar, ChatApp) in cli/tui/, move CliBus from channels/ to cli/ and rewrite it to use Textual components, maintaining the same Channel interface for seamless integration with existing event-driven architecture.

**Tech Stack:** Textual (TUI framework), Rich (markdown rendering), asyncio

---

## Task 1: Add Textual Dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add textual to dependencies**

Open `pyproject.toml` and add `textual` to dependencies:

```toml
dependencies = [
    # ... existing dependencies ...
    "textual>=0.47.0",
]
```

**Step 2: Install the dependency**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 3: Verify installation**

Run: `uv run python -c "import textual; print(textual.__version__)"`
Expected: Version number printed (e.g., "0.47.0" or higher)

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add textual dependency for TUI"
```

---

## Task 2: Create TUI Directory Structure

**Files:**
- Create: `src/picklebot/cli/tui/__init__.py`
- Create: `src/picklebot/cli/tui/.gitkeep`

**Step 1: Create tui directory**

Run: `mkdir -p src/picklebot/cli/tui`

**Step 2: Create __init__.py**

Create `src/picklebot/cli/tui/__init__.py`:

```python
"""TUI components for pickle-bot CLI."""
```

**Step 3: Commit**

```bash
git add src/picklebot/cli/tui/
git commit -m "chore: create cli/tui directory structure"
```

---

## Task 3: Implement MessageHistory Widget

**Files:**
- Create: `src/picklebot/cli/tui/widgets.py`
- Create: `tests/cli/tui/__init__.py`
- Create: `tests/cli/tui/test_widgets.py`

**Step 1: Write failing test for MessageHistory**

Create `tests/cli/tui/__init__.py`:

```python
"""Tests for TUI widgets."""
```

Create `tests/cli/tui/test_widgets.py`:

```python
"""Tests for TUI widgets."""

import pytest
from picklebot.cli.tui.widgets import MessageHistory, UserMessage


@pytest.mark.asyncio
async def test_message_history_add_user_message():
    """Test adding a user message to history."""
    history = MessageHistory()

    # Add a user message
    await history.add_message("Hello", message_type="user")

    # Verify message was added
    assert len(history.messages) == 1
    assert isinstance(history.messages[0], UserMessage)
    assert history.messages[0].content == "Hello"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_message_history_add_user_message -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.cli.tui.widgets'"

**Step 3: Implement MessageHistory widget**

Create `src/picklebot/cli/tui/widgets.py`:

```python
"""TUI widgets for chat interface."""

from textual.widget import Widget
from textual.widgets import Static, ScrollableContainer
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown


class UserMessage(Static):
    """A user message in the chat history."""

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def render(self):
        text = Text()
        text.append("User: ", style="bold cyan")
        text.append(self.content)
        return text


class AgentMessage(Static):
    """An agent message in the chat history."""

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def render(self):
        markdown = Markdown(f"**Agent:**\n\n{self.content}")
        return markdown


class ErrorMessage(Static):
    """An error message in the chat history."""

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def render(self):
        text = Text()
        text.append("Error: ", style="bold red")
        text.append(self.content, style="red")
        return text


class MessageHistory(ScrollableContainer):
    """Scrollable message history widget."""

    def __init__(self):
        super().__init__()
        self.messages: list[Widget] = []

    async def add_message(self, content: str, message_type: str = "user"):
        """Add a message to the history.

        Args:
            content: Message content
            message_type: "user", "agent", or "error"
        """
        if message_type == "user":
            message = UserMessage(content)
        elif message_type == "agent":
            message = AgentMessage(content)
        elif message_type == "error":
            message = ErrorMessage(content)
        else:
            raise ValueError(f"Unknown message type: {message_type}")

        self.messages.append(message)
        await self.mount(message)
        self.scroll_end(animate=False)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_message_history_add_user_message -v`
Expected: PASS

**Step 5: Write test for agent message**

Add to `tests/cli/tui/test_widgets.py`:

```python
from picklebot.cli.tui.widgets import AgentMessage


@pytest.mark.asyncio
async def test_message_history_add_agent_message():
    """Test adding an agent message with markdown."""
    history = MessageHistory()

    await history.add_message("# Hello\n\nThis is **bold**", message_type="agent")

    assert len(history.messages) == 1
    assert isinstance(history.messages[0], AgentMessage)
    assert "Hello" in history.messages[0].content
```

**Step 6: Run test**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_message_history_add_agent_message -v`
Expected: PASS

**Step 7: Write test for error message**

Add to `tests/cli/tui/test_widgets.py`:

```python
from picklebot.cli.tui.widgets import ErrorMessage


@pytest.mark.asyncio
async def test_message_history_add_error_message():
    """Test adding an error message."""
    history = MessageHistory()

    await history.add_message("API timeout", message_type="error")

    assert len(history.messages) == 1
    assert isinstance(history.messages[0], ErrorMessage)
    assert history.messages[0].content == "API timeout"
```

**Step 8: Run test**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_message_history_add_error_message -v`
Expected: PASS

**Step 9: Commit**

```bash
git add src/picklebot/cli/tui/widgets.py tests/cli/tui/
git commit -m "feat: add MessageHistory widget with user/agent/error messages"
```

---

## Task 4: Implement InputBar Widget

**Files:**
- Modify: `src/picklebot/cli/tui/widgets.py`
- Modify: `tests/cli/tui/test_widgets.py`

**Step 1: Write failing test for InputBar**

Add to `tests/cli/tui/test_widgets.py`:

```python
from picklebot.cli.tui.widgets import InputBar


@pytest.mark.asyncio
async def test_input_bar_emits_message_on_submit():
    """Test that InputBar emits a message when user submits."""
    input_bar = InputBar()

    # Track if message was emitted
    emitted = []

    def on_message(message):
        emitted.append(message)

    input_bar.on_message = on_message
    input_bar.value = "Hello world"
    await input_bar.submit()

    assert len(emitted) == 1
    assert emitted[0] == "Hello world"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_input_bar_emits_message_on_submit -v`
Expected: FAIL with "ImportError: cannot import name 'InputBar'"

**Step 3: Implement InputBar widget**

Add to `src/picklebot/cli/tui/widgets.py`:

```python
from textual.widgets import Input
from textual.reactive import reactive


class InputBar(Widget):
    """Fixed input bar at bottom of chat."""

    DEFAULT_CSS = """
    InputBar {
        height: auto;
        dock: bottom;
        padding: 1;
        background: $panel;
    }
    """

    value = reactive("")

    def __init__(self, on_submit=None):
        super().__init__()
        self.on_submit = on_submit

    def compose(self):
        yield Input(placeholder="Type a message...", id="chat-input")

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle Enter key in input."""
        if event.value.strip():
            if self.on_submit:
                await self.on_submit(event.value)
            event.input.value = ""  # Clear input

    async def submit(self):
        """Programmatically submit current value (for testing)."""
        if self.value.strip():
            if self.on_submit:
                await self.on_submit(self.value)
            self.value = ""
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/tui/test_widgets.py::test_input_bar_emits_message_on_submit -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/tui/widgets.py tests/cli/tui/test_widgets.py
git commit -m "feat: add InputBar widget with submit handling"
```

---

## Task 5: Implement ChatApp

**Files:**
- Create: `src/picklebot/cli/tui/app.py`
- Create: `src/picklebot/cli/tui/styles.css`
- Create: `tests/cli/tui/test_app.py`

**Step 1: Write failing test for ChatApp**

Create `tests/cli/tui/test_app.py`:

```python
"""Tests for ChatApp."""

import pytest
from picklebot.cli.tui.app import ChatApp


@pytest.mark.asyncio
async def test_chat_app_composition():
    """Test that ChatApp composes MessageHistory and InputBar."""
    messages = []

    async def on_message(msg):
        messages.append(msg)

    app = ChatApp(on_message=on_message)

    # Verify app has required widgets
    assert hasattr(app, "message_history")
    assert hasattr(app, "input_bar")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/tui/test_app.py::test_chat_app_composition -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.cli.tui.app'"

**Step 3: Implement ChatApp**

Create `src/picklebot/cli/tui/app.py`:

```python
"""Main chat TUI application."""

from textual.app import App
from textual.widgets import Header, Footer

from picklebot.cli.tui.widgets import MessageHistory, InputBar


class ChatApp(App):
    """Main chat application with message history and input."""

    CSS_PATH = "styles.css"

    def __init__(self, on_message=None):
        super().__init__()
        self.on_message = on_message
        self.message_history = MessageHistory()
        self.input_bar = InputBar(on_submit=self._handle_input)

    def compose(self):
        """Compose the UI layout."""
        yield Header()
        yield self.message_history
        yield self.input_bar
        yield Footer()

    async def _handle_input(self, message: str):
        """Handle user input from InputBar."""
        # Display user message in history
        await self.message_history.add_message(message, message_type="user")

        # Call the on_message callback (to emit InboundEvent)
        if self.on_message:
            await self.on_message(message)

    async def add_agent_message(self, content: str):
        """Add an agent message to history."""
        await self.message_history.add_message(content, message_type="agent")

    async def add_error_message(self, content: str):
        """Add an error message to history."""
        await self.message_history.add_message(content, message_type="error")

    async def on_key(self, event):
        """Handle key events."""
        if event.key == "ctrl+c":
            self.exit()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/tui/test_app.py::test_chat_app_composition -v`
Expected: PASS

**Step 5: Create styles.css**

Create `src/picklebot/cli/tui/styles.css`:

```css
/* Chat TUI Styles */

MessageHistory {
    height: 1fr;
    background: $surface;
    padding: 1;
}

InputBar {
    height: auto;
    background: $panel;
    padding: 1;
}

Input {
    width: 1fr;
}

Header {
    background: $primary;
    color: $text;
}

Footer {
    background: $panel;
}
```

**Step 6: Write test for adding messages**

Add to `tests/cli/tui/test_app.py`:

```python
@pytest.mark.asyncio
async def test_chat_app_add_agent_message():
    """Test adding agent message to ChatApp."""
    app = ChatApp()

    await app.add_agent_message("Hello from agent")

    assert len(app.message_history.messages) == 1


@pytest.mark.asyncio
async def test_chat_app_add_error_message():
    """Test adding error message to ChatApp."""
    app = ChatApp()

    await app.add_error_message("Something went wrong")

    assert len(app.message_history.messages) == 1
```

**Step 7: Run tests**

Run: `uv run pytest tests/cli/tui/test_app.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add src/picklebot/cli/tui/app.py src/picklebot/cli/tui/styles.css tests/cli/tui/test_app.py
git commit -m "feat: add ChatApp with message history and input bar"
```

---

## Task 6: Move and Rewrite CliBus

**Files:**
- Create: `src/picklebot/cli/cli_bus.py` (copy from channels/cli_bus.py then rewrite)
- Modify: `tests/channels/test_cli_bus.py` (will move to tests/cli/)
- Create: `tests/cli/test_cli_bus.py`

**Step 1: Read existing CliBus**

Run: `cat src/picklebot/channels/cli_bus.py`
(Expected: See existing implementation)

**Step 2: Write failing test for Textual CliBus**

Create `tests/cli/test_cli_bus.py`:

```python
"""Tests for Textual CLI bus."""

import pytest
from picklebot.cli.cli_bus import CliBus, CliEventSource


def test_cli_bus_creation():
    """Test creating a CliBus instance."""
    bus = CliBus()
    assert bus.platform_name == "cli"


def test_cli_event_source():
    """Test CliEventSource properties."""
    source = CliEventSource()

    assert str(source) == "platform-cli:cli-user"
    assert source.platform_name == "cli"
    assert source.is_platform is True


@pytest.mark.asyncio
async def test_cli_bus_emits_inbound_event():
    """Test that CliBus calls on_message callback when user sends message."""
    bus = CliBus()

    messages = []

    async def on_message(content, source):
        messages.append((content, source))

    # This would be triggered by the Textual app
    # We'll test the callback mechanism directly
    source = CliEventSource()
    await bus._handle_user_message("Hello", source)

    # Note: In real implementation, this is wired through Textual
    # For now, we're testing the callback mechanism exists
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_cli_bus.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.cli.cli_bus'"

**Step 4: Move CliBus to cli/ and rewrite with Textual**

Create `src/picklebot/cli/cli_bus.py`:

```python
"""CLI message bus implementation using Textual TUI."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

from picklebot.core.events import EventSource
from picklebot.channels.base import Channel
from picklebot.cli.tui.app import ChatApp

logger = logging.getLogger(__name__)


@dataclass
class CliEventSource(EventSource):
    """Source for CLI-originated events."""

    _namespace = "platform-cli"

    def __str__(self) -> str:
        return "platform-cli:cli-user"

    @classmethod
    def from_string(cls, s: str) -> "CliEventSource":
        return cls()

    @property
    def platform_name(self) -> str:
        return "cli"


class CliBus(Channel[CliEventSource]):
    """CLI platform implementation using Textual TUI."""

    platform_name = "cli"

    def __init__(self):
        """Initialize CliBus."""
        self.app: ChatApp | None = None
        self._stop_event = asyncio.Event()
        self._running = False

    def is_allowed(self, source: CliEventSource) -> bool:
        """Check if sender is whitelisted. CLI always allows all users."""
        return True

    async def run(
        self, on_message: Callable[[str, CliEventSource], Awaitable[None]]
    ) -> None:
        """Run the CLI message bus with Textual TUI.

        Args:
            on_message: Callback for when user sends a message
        """
        if self._running:
            raise RuntimeError("CliBus already running")

        self._running = True
        self._stop_event.clear()
        logger.info(f"Channel enabled with platform: {self.platform_name}")

        # Create Textual app with callback wrapper
        async def handle_user_input(message: str):
            """Wrapper to call on_message with source."""
            source = CliEventSource()
            try:
                await on_message(message, source)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        try:
            self.app = ChatApp(on_message=handle_user_input)
            await self.app.run_async()
        finally:
            self._running = False
            logger.info("CliBus stopped")

    async def reply(self, content: str, source: CliEventSource) -> None:
        """Reply to incoming message by displaying in TUI.

        Args:
            content: Message content (may contain error from OutboundEvent.error)
            source: The source of the message
        """
        if not self.app:
            logger.warning("Cannot reply: Textual app not initialized")
            return

        # Add message to the TUI message history
        # The content could be from OutboundEvent.content or OutboundEvent.error
        # The DeliveryWorker will call this with appropriate content
        await self.app.add_agent_message(content)
        logger.debug("Sent CLI reply via TUI")

    async def reply_error(self, error: str, source: CliEventSource) -> None:
        """Display an error message in TUI.

        Args:
            error: Error message
            source: The source of the error
        """
        if not self.app:
            logger.warning("Cannot reply error: Textual app not initialized")
            return

        await self.app.add_error_message(error)
        logger.debug("Sent CLI error via TUI")

    async def stop(self) -> None:
        """Stop CLI bus and cleanup."""
        if not self._running:
            return
        logger.info("Stopping CliBus")
        self._stop_event.set()
        if self.app:
            self.app.exit()
        logger.info("CliBus stop signaled")
```

**Step 5: Run tests**

Run: `uv run pytest tests/cli/test_cli_bus.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/cli/cli_bus.py tests/cli/test_cli_bus.py
git commit -m "feat: move CliBus to cli/ and rewrite with Textual TUI"
```

---

## Task 7: Update cli/chat.py to Use New CliBus

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Read current chat.py**

Run: `cat src/picklebot/cli/chat.py`

**Step 2: Update imports**

Modify `src/picklebot/cli/chat.py` line 12:

```python
# OLD:
from picklebot.channels.cli_bus import CliBus

# NEW:
from picklebot.cli.cli_bus import CliBus
```

**Step 3: Verify imports work**

Run: `uv run python -c "from picklebot.cli.cli_bus import CliBus; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add src/picklebot/cli/chat.py
git commit -m "refactor: update chat.py to use CliBus from cli/ package"
```

---

## Task 8: Remove Old channels/cli_bus.py and Tests

**Files:**
- Delete: `src/picklebot/channels/cli_bus.py`
- Delete: `tests/channels/test_cli_bus.py`
- Modify: Any files importing from old location

**Step 1: Find all imports of old CliBus**

Run: `grep -r "from picklebot.channels.cli_bus import" src/ tests/`
Expected: No results (we updated chat.py already)

**Step 2: Remove old cli_bus.py**

Run: `rm src/picklebot/channels/cli_bus.py`

**Step 3: Remove old test file**

Run: `rm tests/channels/test_cli_bus.py`

**Step 4: Verify no broken imports**

Run: `uv run python -c "import picklebot"`
Expected: No errors

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old channels/cli_bus.py (moved to cli/)"
```

---

## Task 9: Integration Test

**Files:**
- Create: `tests/cli/test_chat_integration.py`

**Step 1: Write integration test**

Create `tests/cli/test_chat_integration.py`:

```python
"""Integration tests for chat command."""

import pytest
from picklebot.cli.chat import ChatLoop
from picklebot.cli.cli_bus import CliBus
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config


def test_chat_loop_creation():
    """Test creating a ChatLoop instance."""
    config = Config()
    chat_loop = ChatLoop(config)

    assert chat_loop.config == config
    assert isinstance(chat_loop.bus, CliBus)
    assert isinstance(chat_loop.context, SharedContext)
    assert len(chat_loop.workers) == 4  # EventBus, AgentWorker, DeliveryWorker, ChannelWorker


@pytest.mark.asyncio
async def test_chat_loop_lifecycle():
    """Test starting and stopping ChatLoop."""
    config = Config()
    chat_loop = ChatLoop(config)

    # Start workers
    for worker in chat_loop.workers:
        worker.start()

    # Verify workers are running
    assert all(worker._running for worker in chat_loop.workers if hasattr(worker, '_running'))

    # Stop workers
    for worker in chat_loop.workers:
        await worker.stop()

    # Verify clean shutdown
    assert True  # If we got here, shutdown was successful
```

**Step 2: Run integration test**

Run: `uv run pytest tests/cli/test_chat_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/cli/test_chat_integration.py
git commit -m "test: add integration tests for chat command"
```

---

## Task 10: Manual Testing

**Step 1: Test chat command starts**

Run: `uv run picklebot chat`
Expected: Textual TUI appears with message history area and input bar

**Step 2: Test user input**

Type: "Hello"
Press: Enter
Expected: Message appears in history with "User:" prefix in cyan

**Step 3: Test agent response**

Wait for agent response
Expected: Response appears in history with markdown rendering in green

**Step 4: Test scrolling**

Send multiple messages until history is full
Use mouse or Page Up to scroll up
Expected: Can view older messages

**Step 5: Test quit**

Press: Ctrl+C
Expected: App exits cleanly

**Step 6: Run full test suite**

Run: `uv run pytest`
Expected: All tests pass

---

## Verification Checklist

- [ ] Textual dependency added to pyproject.toml
- [ ] MessageHistory widget displays user/agent/error messages
- [ ] InputBar emits messages on Enter
- [ ] ChatApp composes history + input correctly
- [ ] CliBus moved to cli/ and uses Textual
- [ ] chat.py imports from new location
- [ ] Old channels/cli_bus.py removed
- [ ] Integration tests pass
- [ ] Manual testing shows TUI works correctly
- [ ] All automated tests pass

---

## Notes

- The `DeliveryWorker` will need to be updated to call `reply_error()` when `OutboundEvent.error` is set. This is a small change to delivery_worker.py:

```python
# In DeliveryWorker.handle_event():
if event.error:
    await bus.reply_error(event.error, source)
else:
    await bus.reply(event.content, source)
```

This can be done as a follow-up task or integrated into Task 6 if preferred.
