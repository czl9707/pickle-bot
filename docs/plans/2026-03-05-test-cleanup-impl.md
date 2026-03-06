# Test Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce trivial tests and consolidate into meaningful roundtrip tests in `tests/events/` module.

**Architecture:** Replace individual "creation + property check" tests with parametrized roundtrip tests. Delete stub tests. Keep logic tests.

**Tech Stack:** pytest, pytest.mark.parametrize

---

## Task 1: Rewrite test_source.py

**Files:**
- Modify: `tests/events/test_source.py` (rewrite entirely)
- Test: `tests/events/test_source.py`

**Step 1: Write the new parametrized roundtrip test**

Replace entire file with:

```python
"""Tests for EventSource hierarchy."""

import pytest

from picklebot.core.events import EventSource, AgentEventSource, CronEventSource, CliEventSource
from picklebot.channel.telegram_channel import TelegramEventSource
from picklebot.channel.discord_channel import DiscordEventSource


class TestEventSourceBase:
    """Tests for EventSource ABC behavior."""

    def test_cannot_instantiate_abstract_base(self):
        """EventSource should not be directly instantiable."""
        with pytest.raises(TypeError):
            EventSource()

    def test_from_string_raises_on_unknown_namespace(self):
        """from_string should raise for unregistered namespace."""
        with pytest.raises(ValueError, match="Unknown source namespace"):
            EventSource.from_string("unknown:value")


class TestSourceRoundtrip:
    """Parametrized roundtrip tests for all EventSource types."""

    @pytest.mark.parametrize("source_cls,args,expected_str,type_props", [
        (
            AgentEventSource,
            {"agent_id": "pickle"},
            "agent:pickle",
            {"is_agent": True, "is_platform": False, "is_cron": False, "platform_name": None},
        ),
        (
            CronEventSource,
            {"cron_id": "daily-summary"},
            "cron:daily-summary",
            {"is_agent": False, "is_platform": False, "is_cron": True, "platform_name": None},
        ),
        (
            TelegramEventSource,
            {"user_id": "12345", "chat_id": "67890"},
            "platform-telegram:12345:67890",
            {"is_agent": False, "is_platform": True, "is_cron": False, "platform_name": "telegram"},
        ),
        (
            DiscordEventSource,
            {"user_id": "12345", "channel_id": "67890"},
            "platform-discord:12345:67890",
            {"is_agent": False, "is_platform": True, "is_cron": False, "platform_name": "discord"},
        ),
        (
            CliEventSource,
            {},
            "platform-cli:cli-user",
            {"is_agent": False, "is_platform": True, "is_cron": False, "platform_name": "cli"},
        ),
    ])
    def test_source_roundtrip(self, source_cls, args, expected_str, type_props):
        """Source should serialize/deserialize and have correct type properties."""
        # Create
        source = source_cls(**args)

        # Check serialization
        assert str(source) == expected_str

        # Check roundtrip via class method
        restored = source_cls.from_string(expected_str)
        for key, value in args.items():
            assert getattr(restored, key) == value

        # Check roundtrip via base class
        restored_via_base = EventSource.from_string(expected_str)
        assert isinstance(restored_via_base, source_cls)

        # Check type properties
        for prop, expected in type_props.items():
            assert getattr(source, prop) == expected
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/events/test_source.py -v`
Expected: All tests pass, count reduced from 12 to 7

**Step 3: Commit**

```bash
git add tests/events/test_source.py
git commit -m "refactor(test): consolidate EventSource tests into parametrized roundtrip"
```

---

## Task 2: Rewrite test_types.py

**Files:**
- Modify: `tests/events/test_types.py` (rewrite entirely)
- Test: `tests/events/test_types.py`

**Step 1: Write the new parametrized roundtrip test**

Replace entire file with:

```python
"""Tests for Event types."""

import pytest

from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    AgentEventSource,
    CronEventSource,
    serialize_event,
    deserialize_event,
)
from picklebot.channel.telegram_channel import TelegramEventSource


class TestEventRoundtrip:
    """Parametrized roundtrip tests for all Event types."""

    @pytest.mark.parametrize("event_cls,extra_args", [
        (InboundEvent, {"retry_count": 0}),
        (OutboundEvent, {"error": None}),
        (DispatchEvent, {"parent_session_id": "parent-1", "retry_count": 0}),
        (DispatchResultEvent, {"error": None}),
    ])
    def test_event_roundtrip(self, event_cls, extra_args):
        """Event should serialize/deserialize with all fields preserved."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        original = event_cls(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Hello",
            timestamp=12345.0,
            **extra_args,
        )

        # Serialize
        data = serialize_event(original)
        assert data["type"] == event_cls.__name__
        assert data["session_id"] == "sess-1"
        assert data["source"] == "platform-telegram:123:456"

        # Deserialize
        restored = deserialize_event(data)
        assert isinstance(restored, event_cls)
        assert restored.session_id == "sess-1"
        assert restored.agent_id == "pickle"
        assert restored.content == "Hello"
        assert isinstance(restored.source, TelegramEventSource)
        assert restored.source.user_id == "123"

        # Check extra args preserved
        for key, value in extra_args.items():
            assert getattr(restored, key) == value

    def test_event_with_error_roundtrip(self):
        """Events with error field should preserve it."""
        source = AgentEventSource(agent_id="pickle")

        # OutboundEvent with error
        outbound = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="",
            timestamp=12345.0,
            error="Something failed",
        )
        data = serialize_event(outbound)
        assert data["error"] == "Something failed"
        restored = deserialize_event(data)
        assert restored.error == "Something failed"

        # DispatchResultEvent with error
        dispatch_result = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source=source,
            content="",
            timestamp=12345.0,
            error="Task failed",
        )
        data = serialize_event(dispatch_result)
        restored = deserialize_event(data)
        assert restored.error == "Task failed"

    def test_unknown_event_type_raises(self):
        """deserialize_event should reject unknown types."""
        data = {
            "type": "unknown_type",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "agent:test",
            "content": "test",
            "timestamp": 12345.0,
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(data)


class TestEventBaseClass:
    """Tests for Event base class behavior."""

    def test_event_auto_timestamp(self):
        """Event should auto-populate timestamp."""
        import time

        before = time.time()
        event = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source=AgentEventSource(agent_id="test"),
            content="hello",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_inbound_event_no_context_field(self):
        """InboundEvent should not have context field after refactor."""
        source = AgentEventSource(agent_id="pickle")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="hello",
        )

        assert not hasattr(event, "context")
        data = serialize_event(event)
        assert "context" not in data
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/events/test_types.py -v`
Expected: All tests pass, count reduced from 26 to 6

**Step 3: Commit**

```bash
git add tests/events/test_types.py
git commit -m "refactor(test): consolidate Event type tests into parametrized roundtrip"
```

---

## Task 3: Delete test_websocket_stub.py

**Files:**
- Delete: `tests/events/test_websocket_stub.py`

**Step 1: Delete the file**

Run: `rm tests/events/test_websocket_stub.py`

**Step 2: Verify tests still pass**

Run: `uv run pytest tests/events/ -v`
Expected: All remaining tests pass

**Step 3: Commit**

```bash
git add tests/events/test_websocket_stub.py
git commit -m "refactor(test): delete trivial WebSocket stub tests"
```

---

## Task 4: Final verification

**Step 1: Run all tests**

Run: `uv run pytest tests/events/ -v`
Expected: All 28 tests pass (down from 64)

**Step 2: Run linting**

Run: `uv run black . && uv run ruff check .`
Expected: No issues

**Step 3: Verify count**

Run: `uv run pytest tests/events/ --collect-only -q`
Expected: 28 tests collected

**Step 4: Final commit (if any formatting changes)**

```bash
git add -A
git commit -m "style: format after test cleanup"
```

---

## Summary

| File | Before | After |
|------|--------|-------|
| `test_source.py` | 152 lines, 12 tests | ~70 lines, 7 tests |
| `test_types.py` | 475 lines, 26 tests | ~100 lines, 6 tests |
| `test_websocket_stub.py` | 57 lines, 3 tests | deleted |
| **Total** | 64 tests | 28 tests |
