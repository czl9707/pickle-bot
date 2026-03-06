# Delivery Worker Retry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add proper retry logic to DeliveryWorker with exponential backoff for failed deliveries.

**Architecture:** Extract a `_deliver_with_retry()` helper method that handles retry attempts with backoff sleep. The method retries all chunks together, and after MAX_RETRIES logs the error and returns False.

**Tech Stack:** asyncio, pytest, unittest.mock

---

### Task 1: Add test for `_deliver_with_retry` success case

**Files:**
- Modify: `tests/server/test_delivery_worker.py`

**Step 1: Write the failing test**

Add to `tests/server/test_delivery_worker.py`:

```python
class TestDeliverWithRetry:
    """Tests for _deliver_with_retry method."""

    @pytest.mark.asyncio
    async def test_deliver_with_retry_success_first_try(self, mock_context):
        """Should return True when delivery succeeds on first attempt."""
        from picklebot.core.events import TelegramEventSource

        worker = DeliveryWorker(mock_context)
        mock_bus = Mock()
        mock_bus.reply = AsyncMock()

        source = TelegramEventSource(chat_id=123, message_id=456)
        chunks = ["Hello"]

        result = await worker._deliver_with_retry(chunks, source, mock_bus)

        assert result is True
        mock_bus.reply.assert_called_once_with("Hello", source)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDeliverWithRetry::test_deliver_with_retry_success_first_try -v`
Expected: FAIL with "AttributeError: 'DeliveryWorker' object has no attribute '_deliver_with_retry'"

---

### Task 2: Implement `_deliver_with_retry` method

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py:98` (in DeliveryWorker class)

**Step 1: Add asyncio import**

At the top of `src/picklebot/server/delivery_worker.py`, add `asyncio` to imports:

```python
import asyncio
import logging
import random
```

**Step 2: Add the `_deliver_with_retry` method**

Add this method to the `DeliveryWorker` class (after `__init__`):

```python
    async def _deliver_with_retry(
        self, chunks: list[str], source: "EventSource", bus: "Channel[Any]"
    ) -> bool:
        """Deliver all chunks with retry logic. Returns True on success."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                for chunk in chunks:
                    await bus.reply(chunk, source)
                return True
            except Exception as e:
                if attempt < MAX_RETRIES:
                    backoff_ms = compute_backoff_ms(attempt)
                    self.logger.warning(
                        f"Delivery failed (attempt {attempt}/{MAX_RETRIES}), "
                        f"retrying in {backoff_ms}ms: {e}"
                    )
                    await asyncio.sleep(backoff_ms / 1000)
                else:
                    self.logger.error(f"Delivery failed after {MAX_RETRIES} attempts: {e}")
                    return False
        return False
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDeliverWithRetry::test_deliver_with_retry_success_first_try -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/server/delivery_worker.py tests/server/test_delivery_worker.py
git commit -m "feat: add _deliver_with_retry method to DeliveryWorker"
```

---

### Task 3: Add test for retry on failure

**Files:**
- Modify: `tests/server/test_delivery_worker.py`

**Step 1: Write the test**

Add to `TestDeliverWithRetry` class:

```python
    @pytest.mark.asyncio
    async def test_deliver_with_retry_retries_on_failure(self, mock_context):
        """Should retry with backoff when delivery fails."""
        from picklebot.core.events import TelegramEventSource

        worker = DeliveryWorker(mock_context)
        mock_bus = Mock()
        # Fail twice, then succeed
        mock_bus.reply = AsyncMock(side_effect=[Exception("Network error"), None])

        source = TelegramEventSource(chat_id=123, message_id=456)
        chunks = ["Hello"]

        # Patch asyncio.sleep to avoid actual delay
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await worker._deliver_with_retry(chunks, source, mock_bus)

        assert result is True
        assert mock_bus.reply.call_count == 2
        mock_sleep.assert_called_once()  # One sleep between retries
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDeliverWithRetry::test_deliver_with_retry_retries_on_failure -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/server/test_delivery_worker.py
git commit -m "test: add test for retry on failure in _deliver_with_retry"
```

---

### Task 4: Add test for max retries exceeded

**Files:**
- Modify: `tests/server/test_delivery_worker.py`

**Step 1: Write the test**

Add to `TestDeliverWithRetry` class:

```python
    @pytest.mark.asyncio
    async def test_deliver_with_retry_returns_false_after_max_retries(self, mock_context):
        """Should return False after MAX_RETRIES failures."""
        from picklebot.core.events import TelegramEventSource

        worker = DeliveryWorker(mock_context)
        mock_bus = Mock()
        mock_bus.reply = AsyncMock(side_effect=Exception("Permanent failure"))

        source = TelegramEventSource(chat_id=123, message_id=456)
        chunks = ["Hello"]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await worker._deliver_with_retry(chunks, source, mock_bus)

        assert result is False
        assert mock_bus.reply.call_count == MAX_RETRIES
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDeliverWithRetry::test_deliver_with_retry_returns_false_after_max_retries -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/server/test_delivery_worker.py
git commit -m "test: add test for max retries exceeded"
```

---

### Task 5: Add test for chunk retry behavior

**Files:**
- Modify: `tests/server/test_delivery_worker.py`

**Step 1: Write the test**

Add to `TestDeliverWithRetry` class:

```python
    @pytest.mark.asyncio
    async def test_deliver_with_retry_retries_all_chunks_on_failure(self, mock_context):
        """Should retry all chunks from scratch when any chunk fails."""
        from picklebot.core.events import TelegramEventSource

        worker = DeliveryWorker(mock_context)
        mock_bus = Mock()
        # First chunk succeeds, second fails, then both succeed
        call_count = 0

        async def side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second chunk on first attempt fails
                raise Exception("Chunk failed")

        mock_bus.reply = AsyncMock(side_effect=side_effect)

        source = TelegramEventSource(chat_id=123, message_id=456)
        chunks = ["Chunk 1", "Chunk 2"]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await worker._deliver_with_retry(chunks, source, mock_bus)

        assert result is True
        # First attempt: 2 calls (chunk 1 ok, chunk 2 fails)
        # Retry: 2 calls (both ok)
        assert mock_bus.reply.call_count == 4
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py::TestDeliverWithRetry::test_deliver_with_retry_retries_all_chunks_on_failure -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/server/test_delivery_worker.py
git commit -m "test: add test for chunk retry behavior"
```

---

### Task 6: Refactor `handle_event` to use `_deliver_with_retry`

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py:114-149`

**Step 1: Update `handle_event` method**

Replace the current `handle_event` method with:

```python
    async def handle_event(self, event: OutboundEvent) -> None:
        """Handle an outbound message event."""
        try:
            session_info = self._get_session_source(event.session_id)

            if not session_info or not session_info.source:
                self.logger.warning(
                    f"No source for session {event.session_id}, skipping delivery"
                )
                return

            source = self._get_delivery_source(session_info)
            if not source or not source.platform_name:
                self.context.eventbus.ack(event)
                return

            limit = PLATFORM_LIMITS.get(source.platform_name, float("inf"))
            chunks = chunk_message(event.content, int(limit) if limit != float("inf") else len(event.content))

            bus = self._get_bus(source.platform_name)
            if bus:
                success = await self._deliver_with_retry(chunks, source, bus)
                if not success:
                    self.logger.error(f"Dropped message for session {event.session_id}")

            self.context.eventbus.ack(event)
            self.logger.info(
                f"Delivered message to {source.platform_name} for session {event.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")
```

**Step 2: Run all delivery worker tests**

Run: `uv run pytest tests/server/test_delivery_worker.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/picklebot/server/delivery_worker.py
git commit -m "refactor: use _deliver_with_retry in handle_event"
```

---

### Task 7: Run full test suite and format

**Step 1: Run all tests**

Run: `uv run pytest`
Expected: All PASS

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete delivery worker retry implementation"
```
