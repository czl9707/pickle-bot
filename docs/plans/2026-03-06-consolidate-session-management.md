# Consolidate Session Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate duplicated session management logic from ChannelWorker and WebSocketWorker into RoutingTable.

**Architecture:** Add a single `get_or_create_session_id()` method to RoutingTable that handles session cache lookup and creation. Workers call this method instead of duplicated internal methods. Session storage remains in config.

**Tech Stack:** Python, pytest, dataclasses

---

## Task 1: Test RoutingTable Session Cache Hit

**Files:**
- Modify: `tests/core/test_routing.py`
- Reference: `src/picklebot/core/routing.py`

**Step 1: Write the failing test for cache hit**

Add to `tests/core/test_routing.py`:

```python
def test_get_or_create_session_id_cache_hit(mock_context):
    """Test that existing session_id is returned from cache without creating new session."""
    from picklebot.core.events import TelegramEventSource
    from picklebot.core.routing import RoutingTable

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(chat_id=123, message_id=456)
    agent_id = "test-agent"
    existing_session_id = "existing-session-789"

    # Pre-populate cache
    mock_context.config.sources[str(source)] = {"session_id": existing_session_id}

    # Execute
    result = routing.get_or_create_session_id(source, agent_id)

    # Verify
    assert result == existing_session_id
    # Ensure no new session was created
    mock_context.agent_loader.load.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_routing.py::test_get_or_create_session_id_cache_hit -v`

Expected: FAIL with "RoutingTable object has no attribute 'get_or_create_session_id'"

**Step 3: Commit the failing test**

```bash
git add tests/core/test_routing.py
git commit -m "test: add test for RoutingTable session cache hit"
```

---

## Task 2: Implement RoutingTable Method Stub

**Files:**
- Modify: `src/picklebot/core/routing.py:1-75`

**Step 1: Add required imports**

Add to imports at top of `src/picklebot/core/routing.py`:

```python
from picklebot.core.agent import Agent
from picklebot.core.events import EventSource
```

**Step 2: Add method stub to RoutingTable class**

Add to `RoutingTable` class in `src/picklebot/core/routing.py` after the `resolve` method:

```python
def get_or_create_session_id(self, source: EventSource, agent_id: str) -> str:
    """Get existing session_id from source cache, or create new session.

    Args:
        source: Typed EventSource object
        agent_id: Agent identifier to use for session creation

    Returns:
        session_id: Existing or newly created session identifier
    """
    source_str = str(source)

    # Check cache first
    source_info = self._context.config.sources.get(source_str)
    if source_info:
        return source_info["session_id"]

    # Create new session
    agent_def = self._context.agent_loader.load(agent_id)
    agent = Agent(agent_def, self._context)
    session = agent.new_session(source)

    # Cache the session
    self._context.config.set_runtime(
        f"sources.{source_str}",
        {"session_id": session.session_id}
    )

    return session.session_id
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py::test_get_or_create_session_id_cache_hit -v`

Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/core/routing.py
git commit -m "feat: add get_or_create_session_id to RoutingTable"
```

---

## Task 3: Test RoutingTable Session Creation

**Files:**
- Modify: `tests/core/test_routing.py`

**Step 1: Write the failing test for session creation**

Add to `tests/core/test_routing.py`:

```python
def test_get_or_create_session_id_creates_new_session(mock_context):
    """Test that new session is created when not in cache."""
    from picklebot.core.events import TelegramEventSource
    from picklebot.core.routing import RoutingTable
    from unittest.mock import MagicMock

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(chat_id=123, message_id=456)
    agent_id = "test-agent"
    new_session_id = "new-session-789"

    # Mock agent creation
    mock_agent_def = MagicMock()
    mock_context.agent_loader.load.return_value = mock_agent_def

    mock_session = MagicMock()
    mock_session.session_id = new_session_id

    mock_agent = MagicMock()
    mock_agent.new_session.return_value = mock_session

    # Mock Agent constructor
    with patch('picklebot.core.routing.Agent', return_value=mock_agent) as mock_agent_class:
        # Execute
        result = routing.get_or_create_session_id(source, agent_id)

        # Verify
        assert result == new_session_id
        mock_context.agent_loader.load.assert_called_once_with(agent_id)
        mock_agent_class.assert_called_once_with(mock_agent_def, mock_context)
        mock_agent.new_session.assert_called_once_with(source)

        # Verify cache update
        expected_cache_key = f"sources.{str(source)}"
        mock_context.config.set_runtime.assert_called_once_with(
            expected_cache_key,
            {"session_id": new_session_id}
        )
```

**Step 2: Add missing import**

Add to imports in `tests/core/test_routing.py`:

```python
from unittest.mock import patch
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py::test_get_or_create_session_id_creates_new_session -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/core/test_routing.py
git commit -m "test: add test for RoutingTable session creation"
```

---

## Task 4: Test Exception Propagation

**Files:**
- Modify: `tests/core/test_routing.py`

**Step 1: Write test for exception propagation**

Add to `tests/core/test_routing.py`:

```python
def test_get_or_create_session_id_propagates_agent_not_found(mock_context):
    """Test that exceptions from agent loading are propagated."""
    from picklebot.core.events import TelegramEventSource
    from picklebot.core.routing import RoutingTable

    # Setup
    routing = RoutingTable(mock_context)
    source = TelegramEventSource(chat_id=123, message_id=456)
    agent_id = "nonexistent-agent"

    # Mock agent loader to raise exception
    mock_context.agent_loader.load.side_effect = FileNotFoundError("Agent not found")

    # Execute & Verify
    with pytest.raises(FileNotFoundError, match="Agent not found"):
        routing.get_or_create_session_id(source, agent_id)
```

**Step 2: Add missing import**

Add to imports in `tests/core/test_routing.py`:

```python
import pytest
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py::test_get_or_create_session_id_propagates_agent_not_found -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/core/test_routing.py
git commit -m "test: add test for exception propagation in session creation"
```

---

## Task 5: Update ChannelWorker

**Files:**
- Modify: `src/picklebot/server/channel_worker.py`
- Reference: `src/picklebot/core/routing.py`

**Step 1: Locate duplicated method**

Find the `_get_or_create_session_id` method in `src/picklebot/server/channel_worker.py`.

**Step 2: Remove duplicated method**

Delete the entire `_get_or_create_session_id` method from ChannelWorker.

**Step 3: Update call sites to use RoutingTable**

Find all calls to `self._get_or_create_session_id(source_str, agent_id)` and replace with:

```python
source = EventSource.from_string(source_str)
session_id = self._context.routing.get_or_create_session_id(source, agent_id)
```

**Step 4: Verify no references to removed method**

Run: `grep -n "_get_or_create_session_id" src/picklebot/server/channel_worker.py`

Expected: No matches

**Step 5: Run ChannelWorker tests**

Run: `uv run pytest tests/server/test_channel_worker.py -v`

Expected: All tests PASS (may need to update mocks)

**Step 6: Commit**

```bash
git add src/picklebot/server/channel_worker.py
git commit -m "refactor: use RoutingTable for session management in ChannelWorker"
```

---

## Task 6: Update WebSocketWorker

**Files:**
- Modify: `src/picklebot/server/websocket_worker.py`

**Step 1: Locate duplicated method**

Find the `_get_or_create_session_id` method in `src/picklebot/server/websocket_worker.py`.

**Step 2: Remove duplicated method**

Delete the entire `_get_or_create_session_id` method from WebSocketWorker.

**Step 3: Update call sites to use RoutingTable**

Find all calls to `self._get_or_create_session_id(source, agent_id)` and replace with:

```python
session_id = self._context.routing.get_or_create_session_id(source, agent_id)
```

**Step 4: Verify no references to removed method**

Run: `grep -n "_get_or_create_session_id" src/picklebot/server/websocket_worker.py`

Expected: No matches

**Step 5: Run WebSocketWorker tests**

Run: `uv run pytest tests/server/test_websocket_worker.py -v`

Expected: All tests PASS (may need to update mocks)

**Step 6: Commit**

```bash
git add src/picklebot/server/websocket_worker.py
git commit -m "refactor: use RoutingTable for session management in WebSocketWorker"
```

---

## Task 7: Update Worker Tests

**Files:**
- Modify: `tests/server/test_channel_worker.py`
- Modify: `tests/server/test_websocket_worker.py`

**Step 1: Update ChannelWorker test mocks**

In `tests/server/test_channel_worker.py`, update tests that mock `_get_or_create_session_id` to mock `routing.get_or_create_session_id` instead.

**Step 2: Update WebSocketWorker test mocks**

In `tests/server/test_websocket_worker.py`, update tests that mock `_get_or_create_session_id` to mock `routing.get_or_create_session_id` instead.

**Step 3: Run all worker tests**

Run: `uv run pytest tests/server/ -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/server/test_channel_worker.py tests/server/test_websocket_worker.py
git commit -m "test: update worker tests to mock RoutingTable session method"
```

---

## Task 8: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest`

Expected: All tests PASS

**Step 2: Run linter**

Run: `uv run black . && uv run ruff check .`

Expected: No errors

**Step 3: Fix any issues**

If any linting issues, fix them and commit.

**Step 4: Final verification commit (if needed)**

```bash
git add .
git commit -m "chore: fix linting issues"
```

---

## Task 9: Integration Test

**Files:**
- None (manual verification)

**Step 1: Start the server**

Run: `uv run picklebot server`

Expected: Server starts without errors

**Step 2: Test with a simple message**

Send a test message via CLI or configured platform.

Expected: Message processed correctly, session created and cached.

**Step 3: Verify session caching**

Check that subsequent messages use the same session_id.

Expected: Same session_id returned for same source.

---

## Summary

This plan consolidates session management into RoutingTable through TDD:

1. ✅ Test cache hit behavior
2. ✅ Implement method with full functionality
3. ✅ Test session creation behavior
4. ✅ Test exception propagation
5. ✅ Refactor ChannelWorker to use RoutingTable
6. ✅ Refactor WebSocketWorker to use RoutingTable
7. ✅ Update worker tests
8. ✅ Run full test suite
9. ✅ Integration test

**Result:** ~30 lines of duplicated code eliminated, single responsibility for session management, no behavior changes.
