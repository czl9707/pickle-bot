# Default Delivery Source Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable delivery of agent/cron outbound messages to a default platform source.

**Architecture:** Store a global `default_delivery_source` in runtime config. ChannelWorker sets it on first non-CLI platform message. DeliveryWorker uses it as fallback when source has no platform.

**Tech Stack:** Python, pytest, asyncio

---

## Task 1: Add default_delivery_source field to Config

**Files:**
- Modify: `src/picklebot/utils/config.py:116`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py

def test_config_has_default_delivery_source(test_config):
    """Config should have optional default_delivery_source field."""
    assert hasattr(test_config, "default_delivery_source")
    assert test_config.default_delivery_source is None

def test_config_default_delivery_source_roundtrip(tmp_path, llm_config):
    """default_delivery_source should persist via set_runtime and reload."""
    config = Config(
        workspace=tmp_path,
        llm=llm_config,
        default_agent="test",
    )

    # Set via set_runtime
    config.set_runtime("default_delivery_source", "telegram:user:123:chat:456")

    # Reload and verify
    config.reload()
    assert config.default_delivery_source == "telegram:user:123:chat:456"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_config_has_default_delivery_source tests/test_config.py::test_config_default_delivery_source_roundtrip -v`
Expected: FAIL with AttributeError or assertion error

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/config.py` after line 116 (after `sources` field):

```python
    default_delivery_source: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_config_has_default_delivery_source tests/test_config.py::test_config_default_delivery_source_roundtrip -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/test_config.py
git commit -m "feat(config): add default_delivery_source field"
```

---

## Task 2: Auto-populate default in ChannelWorker

**Files:**
- Modify: `src/picklebot/server/channels_worker.py:58-76`
- Test: `tests/server/test_channels_worker.py`

**Step 1: Write the failing tests**

Add to `tests/server/test_channels_worker.py`:

```python
class TestDefaultDeliverySource:
    """Tests for default_delivery_source auto-population."""

    @pytest.fixture
    def mock_context_with_config(self, mock_context):
        """Mock context with real config for set_runtime."""
        from picklebot.utils.config import Config, LLMConfig

        mock_context.config = Config(
            workspace=Path("/tmp/test-picklebot"),
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="test",
        )
        mock_context.config.default_delivery_source = None
        return mock_context

    @pytest.mark.anyio
    async def test_first_platform_message_sets_default(self, mock_context_with_config):
        """First non-CLI platform message should set default_delivery_source."""
        mock_context = mock_context_with_config
        mock_bus = FakeTelegramBus()
        mock_context.channels_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}

        with patch("picklebot.server.channels_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = ChannelWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"
            callback = worker._create_callback("telegram")

            await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        assert mock_context.config.default_delivery_source == "platform-telegram:123:456"

    @pytest.mark.anyio
    async def test_cli_message_does_not_set_default(self, mock_context_with_config):
        """CLI messages should not update default_delivery_source."""
        mock_context = mock_context_with_config
        mock_bus = FakeCliBus()
        mock_context.channels_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}
        mock_context.config.default_delivery_source = None

        with patch("picklebot.server.channels_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = ChannelWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"

        # CLI should not set default
        assert mock_context.config.default_delivery_source is None

    @pytest.mark.anyio
    async def test_subsequent_message_does_not_overwrite_default(self, mock_context_with_config):
        """Subsequent platform messages should not overwrite existing default."""
        mock_context = mock_context_with_config
        mock_context.config.default_delivery_source = "platform-telegram:existing:999"

        mock_bus = FakeTelegramBus()
        mock_context.channels_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}

        with patch("picklebot.server.channels_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = ChannelWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"
            callback = worker._create_callback("telegram")

            await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        # Should NOT have been overwritten
        assert mock_context.config.default_delivery_source == "platform-telegram:existing:999"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_channels_worker.py::TestDefaultDeliverySource -v`
Expected: FAIL with assertion errors

**Step 3: Write minimal implementation**

Modify `src/picklebot/server/channels_worker.py` in the `_create_callback` method. Add after the slash command handling block (after line 76):

```python
                # Set default delivery source only on first non-CLI platform message
                if source.is_platform and source.platform_name != "cli":
                    if not self.context.config.default_delivery_source:
                        self.context.config.set_runtime(
                            "default_delivery_source", str(source)
                        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_channels_worker.py::TestDefaultDeliverySource -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/channels_worker.py tests/server/test_channels_worker.py
git commit -m "feat(channels): auto-populate default_delivery_source"
```

---

## Task 3: Use default in DeliveryWorker fallback

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py:126-134`
- Test: `tests/server/test_delivery_worker.py`

**Step 1: Write the failing tests**

Add to `tests/server/test_delivery_worker.py`:

```python
class TestDefaultDeliverySource:
    """Tests for default_delivery_source fallback in delivery."""

    @pytest.mark.asyncio
    async def test_uses_default_when_no_platform(self, mock_context):
        """Should deliver to default_delivery_source when session has no platform."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Set default delivery source
        mock_context.config.default_delivery_source = "platform-telegram:123:456"

        # Mock telegram bus
        mock_bus = Mock()
        mock_bus.platform_name = "telegram"
        mock_bus.reply = AsyncMock()
        mock_context.channels_buses = [mock_bus]

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        mock_bus.reply.assert_called_once()
        mock_ack.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_skips_when_no_default_configured(self, mock_context):
        """Should skip with warning when no default_delivery_source configured."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]
        mock_context.config.default_delivery_source = None

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        mock_ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_platform_source_unchanged(self, mock_context):
        """Platform sources should still deliver directly (existing behavior)."""
        from picklebot.core.history import HistorySession

        # Session with platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="platform-telegram:999:888",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Set a different default (should be ignored)
        mock_context.config.default_delivery_source = "platform-discord:111:222"

        # Mock telegram bus only
        mock_bus = Mock()
        mock_bus.platform_name = "telegram"
        mock_bus.reply = AsyncMock()
        mock_context.channels_buses = [mock_bus]

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        # Should deliver to telegram (from session source), not discord (default)
        mock_bus.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_default_logs_error(self, mock_context):
        """Should log error and skip if default_delivery_source is invalid."""
        from picklebot.core.history import HistorySession

        # Session with non-platform source
        mock_session = HistorySession(
            id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            created_at="2026-03-01T10:00:00",
            updated_at="2026-03-01T10:00:00",
        )
        mock_context.history_store.list_sessions.return_value = [mock_session]

        # Invalid default source string
        mock_context.config.default_delivery_source = "invalid:source:format"

        worker = DeliveryWorker(mock_context)
        event = OutboundEvent(
            session_id="session-123",
            agent_id="pickle",
            source="agent:pickle",
            content="Hello",
        )

        with patch.object(mock_context.eventbus, "ack") as mock_ack:
            await worker.handle_event(event)

        # Should skip without acking
        mock_ack.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDefaultDeliverySource -v`
Expected: FAIL with assertion errors

**Step 3: Write minimal implementation**

Modify `src/picklebot/server/delivery_worker.py` lines 126-134. Replace:

```python
            # Get platform name from source
            platform = source.platform_name
            if not platform:
                self.logger.warning(
                    f"Source {session_info.source} is not a platform source, skipping"
                )
                return
```

With:

```python
            # Get platform name from source
            platform = source.platform_name
            if not platform:
                # Try default delivery source for agent/cron events
                default_source_str = self.context.config.default_delivery_source
                if default_source_str:
                    try:
                        source = EventSource.from_string(default_source_str)
                        platform = source.platform_name
                    except ValueError as e:
                        self.logger.error(f"Invalid default_delivery_source: {e}")
                        return
                else:
                    self.logger.warning(
                        f"No platform for session {event.session_id} and no default_delivery_source configured"
                    )
                    return
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDefaultDeliverySource -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/delivery_worker.py tests/server/test_delivery_worker.py
git commit -m "feat(delivery): fallback to default_delivery_source for non-platform events"
```

---

## Task 4: Run full test suite

**Step 1: Run all tests**

Run: `uv run pytest`
Expected: All tests PASS

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: cleanup after default delivery source implementation"
```

---

## Summary

| Task | Files Changed |
|------|---------------|
| 1 | `config.py`, `test_config.py` |
| 2 | `channels_worker.py`, `test_channels_worker.py` |
| 3 | `delivery_worker.py`, `test_delivery_worker.py` |
| 4 | Full test suite verification |
