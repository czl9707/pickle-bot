# Chat Command Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor chat command to use synchronous loop with response queue, eliminating swallowed input, adding proper coloring, and suppressing third-party warnings.

**Architecture:** Remove CliBus abstraction, consolidate all CLI I/O into ChatLoop. ChatLoop drives synchronous interaction: prompt → publish InboundEvent → wait for OutboundEvent queue → display response. EventBus and AgentWorker unchanged.

**Tech Stack:** Rich for styled console I/O, asyncio for event handling, Python warnings module for suppression.

---

## Task 1: Write integration test for chat command flow

**Files:**
- Create: `tests/cli/test_chat_integration.py`

**Step 1: Write the failing test**

```python
"""Integration tests for chat command."""
import asyncio
import pytest
from picklebot.cli.chat import ChatLoop
from picklebot.utils.config import Config
from picklebot.core.events import OutboundEvent, CliEventSource
import time


def test_chat_loop_processes_user_input_and_displays_response():
    """Test that chat loop handles input and displays agent response."""
    config = Config.load()

    chat_loop = ChatLoop(config)

    # Track published events
    published_events = []
    original_publish = chat_loop.context.eventbus.publish

    async def track_publish(event):
        published_events.append(event)
        await original_publish(event)

    chat_loop.context.eventbus.publish = track_publish

    # Simulate chat interaction
    async def run_test():
        # Start workers
        for worker in chat_loop.workers:
            worker.start()

        # Give workers time to start
        await asyncio.sleep(0.1)

        # Simulate user input and agent response
        user_input = "Hello, agent!"

        # Publish inbound event (simulating user input)
        from picklebot.core.events import InboundEvent
        inbound = InboundEvent(
            session_id="test-session",
            agent_id="default",
            source=CliEventSource(),
            content=user_input,
            timestamp=time.time(),
        )
        await chat_loop.context.eventbus.publish(inbound)

        # Simulate agent response
        outbound = OutboundEvent(
            session_id="test-session",
            content="Hello! How can I help you?",
            timestamp=time.time(),
        )
        await chat_loop.context.eventbus.publish(outbound)

        # Wait for response to be queued
        await asyncio.sleep(0.2)

        # Check that inbound event was published
        assert len(published_events) >= 1
        assert published_events[0].content == user_input

        # Cleanup
        for worker in chat_loop.workers:
            await worker.stop()

    asyncio.run(run_test())
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.cli.chat'" or import error

**Step 3: Commit**

```bash
git add tests/cli/test_chat_integration.py
git commit -m "test: add failing integration test for chat command"
```

---

## Task 2: Add Python warning suppression

**Files:**
- Modify: `src/picklebot/cli/chat.py:66-73`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

def test_warnings_are_suppressed():
    """Test that Python warnings are suppressed during chat."""
    import warnings

    # Before chat command, warnings should be active
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.warn("Test warning")
        assert len(w) == 1

    # Import chat module (triggers suppression)
    from picklebot.cli.chat import chat_command

    # After import, warnings should be suppressed
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.warn("Test warning")
        # Should be suppressed
        assert len(w) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_warnings_are_suppressed -v`
Expected: FAIL - warnings not yet suppressed

**Step 3: Implement warning suppression**

```python
# At top of src/picklebot/cli/chat.py
import warnings

# Suppress all warnings at module level
warnings.filterwarnings("ignore")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_warnings_are_suppressed -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "feat(chat): suppress Python warnings"
```

---

## Task 3: Remove CliBus from workers list

**Files:**
- Modify: `src/picklebot/cli/chat.py:23-37`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

def test_chat_loop_has_no_channels_worker():
    """Test that ChatLoop doesn't use ChannelWorker."""
    config = Config.load()
    chat_loop = ChatLoop(config)

    # Check workers list
    worker_types = [type(worker).__name__ for worker in chat_loop.workers]

    # Should have EventBus, AgentWorker, but NOT ChannelWorker or DeliveryWorker
    assert "EventBus" in worker_types
    assert "AgentWorker" in worker_types
    assert "ChannelWorker" not in worker_types
    assert "DeliveryWorker" not in worker_types
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_has_no_channels_worker -v`
Expected: FAIL - ChannelWorker and DeliveryWorker still in list

**Step 3: Remove ChannelWorker and DeliveryWorker**

```python
# In src/picklebot/cli/chat.py, ChatLoop.__init__

def __init__(self, config: Config):
    self.config = config
    self.console = Console()

    # Create SharedContext without buses
    self.context = SharedContext(config=config, buses=[])

    # Create minimal workers for CLI chat
    self.workers: list[Worker] = [
        self.context.eventbus,
        AgentWorker(self.context),
    ]

    # Response queue for collecting agent responses
    self.response_queue: asyncio.Queue[OutboundEvent] = asyncio.Queue()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_has_no_channels_worker -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "refactor(chat): remove ChannelWorker and DeliveryWorker"
```

---

## Task 4: Add OutboundEvent subscription to ChatLoop

**Files:**
- Modify: `src/picklebot/cli/chat.py:23-37`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

@pytest.mark.asyncio
async def test_chat_loop_subscribes_to_outbound_events():
    """Test that ChatLoop subscribes to OutboundEvents."""
    config = Config.load()
    chat_loop = ChatLoop(config)

    # Check subscription exists
    subscribers = chat_loop.context.eventbus._subscribers.get(OutboundEvent, [])
    assert len(subscribers) > 0
    assert chat_loop.handle_outbound_event in subscribers
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_subscribes_to_outbound_events -v`
Expected: FAIL - handle_outbound_event method doesn't exist

**Step 3: Implement event handler and subscription**

```python
# In src/picklebot/cli/chat.py, ChatLoop class

def __init__(self, config: Config):
    self.config = config
    self.console = Console()

    # Create SharedContext without buses
    self.context = SharedContext(config=config, buses=[])

    # Create minimal workers for CLI chat
    self.workers: list[Worker] = [
        self.context.eventbus,
        AgentWorker(self.context),
    ]

    # Response queue for collecting agent responses
    self.response_queue: asyncio.Queue[OutboundEvent] = asyncio.Queue()

    # Subscribe to outbound events
    self.context.eventbus.subscribe(OutboundEvent, self.handle_outbound_event)

async def handle_outbound_event(self, event: OutboundEvent) -> None:
    """Handle outbound events by adding to response queue."""
    await self.response_queue.put(event)
    self.context.eventbus.ack(event)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_subscribes_to_outbound_events -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "feat(chat): add OutboundEvent subscription and handler"
```

---

## Task 5: Implement styled user input method

**Files:**
- Modify: `src/picklebot/cli/chat.py:20-64`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

def test_get_user_input_returns_trimmed_input():
    """Test that get_user_input returns trimmed user input."""
    config = Config.load()
    chat_loop = ChatLoop(config)

    # Mock input
    import io
    import sys

    test_input = "  Hello, agent!  \n"
    sys.stdin = io.StringIO(test_input)

    result = chat_loop.get_user_input()

    assert result == "Hello, agent!"

    # Restore stdin
    sys.stdin = sys.__stdin__
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_get_user_input_returns_trimmed_input -v`
Expected: FAIL - get_user_input method doesn't exist

**Step 3: Implement get_user_input**

```python
# In src/picklebot/cli/chat.py, ChatLoop class

from rich.prompt import Prompt
from rich.text import Text

def get_user_input(self) -> str:
    """Get user input with styled prompt.

    Returns:
        Trimmed user input, or empty string if quit command
    """
    # Create cyan prompt
    prompt_text = Text("You: ", style="cyan")

    # Get input (Prompt.get_input handles the styling)
    user_input = Prompt.ask(prompt_text, console=self.console)

    # Trim whitespace
    user_input = user_input.strip()

    return user_input
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_get_user_input_returns_trimmed_input -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "feat(chat): add styled user input method"
```

---

## Task 6: Implement styled agent response display

**Files:**
- Modify: `src/picklebot/cli/chat.py:20-64`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

from io import StringIO
import sys

def test_display_agent_response_prints_styled_output():
    """Test that display_agent_response prints with green prefix."""
    config = Config.load()
    chat_loop = ChatLoop(config)

    # Capture stdout
    captured_output = StringIO()
    sys.stdout = captured_output

    chat_loop.display_agent_response("Hello! How can I help you?")

    output = captured_output.getvalue()
    sys.stdout = sys.__stdout__

    # Check that output contains the response
    assert "Hello! How can I help you?" in output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_display_agent_response_prints_styled_output -v`
Expected: FAIL - display_agent_response method doesn't exist

**Step 3: Implement display_agent_response**

```python
# In src/picklebot/cli/chat.py, ChatLoop class

from rich.text import Text

def display_agent_response(self, content: str) -> None:
    """Display agent response with styled prefix.

    Args:
        content: Agent response content
    """
    # Create green prefix
    prefix = Text("Agent: ", style="green")

    # Print prefix and content
    self.console.print(prefix, end="")
    self.console.print(content)

    # Add separator line
    self.console.print()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_display_agent_response_prints_styled_output -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "feat(chat): add styled agent response display"
```

---

## Task 7: Implement synchronous chat loop

**Files:**
- Modify: `src/picklebot/cli/chat.py:39-63`

**Step 1: Write the test**

```python
# Add to tests/cli/test_chat_integration.py

@pytest.mark.asyncio
async def test_chat_loop_handles_quit_command():
    """Test that chat loop exits on quit command."""
    config = Config.load()
    chat_loop = ChatLoop(config)

    # Mock input to return 'quit'
    import io
    import sys

    sys.stdin = io.StringIO("quit\n")

    # Start workers
    for worker in chat_loop.workers:
        worker.start()

    # Run chat loop (should exit quickly)
    try:
        await asyncio.wait_for(chat_loop.run(), timeout=1.0)
    except asyncio.TimeoutError:
        # If it times out, quit didn't work
        assert False, "Chat loop didn't exit on quit command"
    finally:
        sys.stdin = sys.__stdin__
        for worker in chat_loop.workers:
            await worker.stop()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_handles_quit_command -v`
Expected: FAIL - run() method not refactored yet

**Step 3: Refactor run() method to synchronous loop**

```python
# In src/picklebot/cli/chat.py, ChatLoop class

async def run(self) -> None:
    """Run the interactive chat loop."""
    # Display welcome message
    self.console.print(
        Panel(
            Text("Welcome to pickle-bot!", style="bold cyan"),
            title="Pickle",
            border_style="cyan",
        )
    )
    self.console.print("Type 'quit' or 'exit' to end the session.\n")

    # Start workers
    for worker in self.workers:
        worker.start()

    try:
        while True:
            # Get user input
            user_input = await asyncio.to_thread(self.get_user_input)

            # Check for quit commands
            if user_input.lower() in ("quit", "exit", "q"):
                self.console.print("\nGoodbye!")
                break

            # Skip empty input
            if not user_input:
                continue

            # Publish InboundEvent
            from picklebot.core.events import InboundEvent
            import time

            # Get or create session (simplified for CLI)
            session_id = "cli-session"

            event = InboundEvent(
                session_id=session_id,
                agent_id="default",
                source=CliEventSource(),
                content=user_input,
                timestamp=time.time(),
            )
            await self.context.eventbus.publish(event)

            # Wait for agent response
            try:
                response = await asyncio.wait_for(
                    self.response_queue.get(),
                    timeout=30.0
                )
                # Display response
                self.display_agent_response(response.content)
            except asyncio.TimeoutError:
                self.console.print("[red]Agent response timed out[/red]")
                self.console.print()

    except (KeyboardInterrupt, EOFError):
        self.console.print("\nGoodbye!")
    finally:
        # Stop all workers gracefully
        for worker in self.workers:
            await worker.stop()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_chat_loop_handles_quit_command -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py tests/cli/test_chat_integration.py
git commit -m "refactor(chat): implement synchronous chat loop"
```

---

## Task 8: Delete CliBus

**Files:**
- Delete: `src/picklebot/channels/cli_bus.py`

**Step 1: Verify no imports of CliBus**

Run: `grep -r "from picklebot.channels.cli_bus import" src/`
Expected: No output (CliBus not imported anywhere)

Run: `grep -r "CliBus" src/picklebot/cli/`
Expected: No output (CliBus not referenced in CLI code)

**Step 2: Delete CliBus file**

```bash
rm src/picklebot/channels/cli_bus.py
```

**Step 3: Verify deletion**

Run: `ls src/picklebot/channels/cli_bus.py`
Expected: Error - file not found

**Step 4: Run tests to ensure nothing broke**

Run: `uv run pytest tests/cli/test_chat_integration.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor(chat): remove CliBus abstraction"
```

---

## Task 9: Remove CliBus from SharedContext if referenced

**Files:**
- Check: `src/picklebot/core/context.py`

**Step 1: Search for CliBus references in context**

Run: `grep -n "CliBus\|cli_bus" src/picklebot/core/context.py`
Expected: No output (CliBus not referenced)

If found, remove the import and any initialization.

**Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 3: Commit if changes were made**

```bash
git add src/picklebot/core/context.py
git commit -m "refactor: remove CliBus from SharedContext"
```

---

## Task 10: Manual integration testing

**Files:**
- N/A (manual testing)

**Step 1: Test chat command manually**

Run: `uv run picklebot chat`

Expected behavior:
- Welcome message appears
- "You: " prompt in cyan
- Type message, press Enter
- "Agent: " appears in green with response
- Blank line separator
- Next "You: " prompt appears
- Type "quit" to exit

**Step 2: Test warning suppression**

Run: `uv run picklebot chat` (check console for warnings)

Expected: No Python warnings appear (e.g., no RequestsDependencyWarning)

**Step 3: Test quit commands**

Try: "quit", "exit", "q", "QUIT", "Exit"

Expected: All quit commands work (case-insensitive)

**Step 4: Test Ctrl+C and Ctrl+D**

Try: Ctrl+C during input

Expected: Graceful exit with "Goodbye!" message

Try: Ctrl+D (EOF)

Expected: Graceful exit with "Goodbye!" message

**Step 5: Test empty input**

Try: Press Enter without typing

Expected: Prompt reappears, no error

**Step 6: Document test results**

Create file: `docs/testing/chat-command-manual-test-results.md`

```markdown
# Chat Command Manual Test Results

Date: 2026-03-03

## Tests

- [x] Basic chat flow works
- [x] Coloring correct (cyan You, green Agent)
- [x] No swallowed input
- [x] Warning suppression works
- [x] Quit commands work
- [x] Ctrl+C graceful exit
- [x] Ctrl+D graceful exit
- [x] Empty input handled

## Issues Found

None.
```

**Step 7: Commit test results**

```bash
git add docs/testing/chat-command-manual-test-results.md
git commit -m "docs: add chat command manual test results"
```

---

## Task 11: Final cleanup and documentation

**Files:**
- Update: `CLAUDE.md` (if needed)
- Update: `docs/architecture.md` (if exists)

**Step 1: Update architecture docs**

Check if `docs/architecture.md` mentions CliBus or chat command.

Run: `grep -n "CliBus\|chat command" docs/architecture.md`

If found, update to reflect new synchronous chat loop design.

**Step 2: Run final test suite**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 3: Run linting**

Run: `uv run black . && uv run ruff check .`

Expected: No errors

**Step 4: Commit final changes**

```bash
git add docs/
git commit -m "docs: update architecture docs for chat command redesign"
```

---

## Success Criteria

- [ ] All tests pass
- [ ] Chat command works with proper coloring
- [ ] No swallowed input issues
- [ ] No Python warnings during chat
- [ ] Quit commands work correctly
- [ ] Graceful exit on Ctrl+C/Ctrl+D
- [ ] CliBus deleted
- [ ] Code formatted and linted
- [ ] Manual testing complete
- [ ] Documentation updated
