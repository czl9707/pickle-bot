# Message Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement unified inbound/outbound message routing with regex-based bindings and simplified configuration.

**Architecture:** New `RoutingTable` class resolves sources to agents using regex bindings with auto-inferred priority tiers. MessageBusWorker uses RoutingTable for inbound routing and source cache for sessions. DeliveryWorker simplified to use HistoryStore with LRU cache, no proactive fallback.

**Tech Stack:** Python dataclasses, functools.lru_cache, re module, Pydantic for config

**Design Doc:** `docs/plans/2026-03-01-message-routing-design.md`

---

## Task 1: Add Config Fields for Routing and Sources

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_config.py

def test_config_has_routing_field(tmp_path):
    """Config should have routing field with bindings."""
    config_data = {
        "workspace": str(tmp_path),
        "llm": {"provider": "zai", "model": "test", "api_key": "test"},
        "default_agent": "pickle",
    }
    config = Config.model_validate(config_data)

    assert config.routing == {"bindings": []}


def test_config_has_sources_field(tmp_path):
    """Config should have sources field for session cache."""
    config_data = {
        "workspace": str(tmp_path),
        "llm": {"provider": "zai", "model": "test", "api_key": "test"},
        "default_agent": "pickle",
    }
    config = Config.model_validate(config_data)

    assert config.sources == {}


def test_config_merges_runtime_routing(tmp_path):
    """Runtime config should merge routing bindings."""
    # Write user config
    user_config = tmp_path / "config.user.yaml"
    user_config.write_text("""
llm:
  provider: zai
  model: test
  api_key: test
default_agent: pickle
""")

    # Write runtime config
    runtime_config = tmp_path / "config.runtime.yaml"
    runtime_config.write_text("""
routing:
  bindings:
    - agent: cookie
      value: "telegram:123456"
sources:
  "telegram:123456":
    session_id: "uuid-abc"
""")

    config = Config.load(tmp_path)

    assert len(config.routing["bindings"]) == 1
    assert config.routing["bindings"][0]["agent"] == "cookie"
    assert config.sources["telegram:123456"]["session_id"] == "uuid-abc"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: FAIL - routing/sources fields not defined

**Step 3: Add fields to Config class**

```python
# src/picklebot/utils/config.py
# Add to Config class fields:

    routing: dict = Field(default_factory=lambda: {"bindings": []})
    sources: dict[str, dict] = Field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add routing and sources fields for message routing"
```

---

## Task 2: Create Binding Dataclass

**Files:**
- Create: `src/picklebot/core/routing.py`
- Test: `tests/core/test_routing.py`

**Step 1: Write the failing test**

```python
# tests/core/test_routing.py

import pytest
from picklebot.core.routing import Binding


def test_binding_compiles_pattern():
    """Binding should compile value into regex pattern."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.pattern.match("telegram:123456")
    assert not binding.pattern.match("telegram:789")


def test_binding_tier_literal():
    """Literal strings should be tier 0 (most specific)."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.tier == 0


def test_binding_tier_specific_regex():
    """Specific regex patterns should be tier 1."""
    binding = Binding(agent="pickle", value="telegram:[0-9]+")

    assert binding.tier == 1


def test_binding_tier_wildcard():
    """Wildcard patterns (.*) should be tier 2 (least specific)."""
    binding = Binding(agent="pickle", value="telegram:.*")

    assert binding.tier == 2


def test_binding_tier_catch_all():
    """Catch-all pattern should be tier 2."""
    binding = Binding(agent="pickle", value=".*")

    assert binding.tier == 2


def test_binding_matches_full_string():
    """Pattern should match full string (anchored)."""
    binding = Binding(agent="pickle", value="telegram:123")

    assert binding.pattern.match("telegram:123")
    assert not binding.pattern.match("telegram:123456")  # extra chars
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_routing.py -v`
Expected: FAIL - module not found

**Step 3: Create Binding dataclass**

```python
# src/picklebot/core/routing.py

import re
from dataclasses import dataclass, field
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


@dataclass
class Binding:
    """A routing binding that matches sources to agents."""

    agent: str
    value: str
    tier: int = field(init=False)
    pattern: Pattern = field(init=False)

    def __post_init__(self):
        self.pattern = re.compile(f"^{self.value}$")
        self.tier = self._compute_tier()

    def _compute_tier(self) -> int:
        """
        Compute specificity tier.

        0 = exact literal (no regex special chars)
        1 = specific regex (anchors, character classes)
        2 = wildcard (. or .*)
        """
        if not any(c in self.value for c in r".*+?[]()|^$"):
            return 0
        if ".*" in self.value:
            return 2
        return 1
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/routing.py tests/core/test_routing.py
git commit -m "feat(routing): add Binding dataclass with tier computation"
```

---

## Task 3: Create RoutingTable Class

**Files:**
- Modify: `src/picklebot/core/routing.py`
- Test: `tests/core/test_routing.py`

**Step 1: Write the failing test**

```python
# tests/core/test_routing.py (append to existing)

from picklebot.core.routing import RoutingTable


class MockConfig:
    def __init__(self, bindings):
        self.routing = {"bindings": bindings}


class MockContext:
    def __init__(self, bindings):
        self.config = MockConfig(bindings)


def test_routing_table_resolve_exact_match():
    """RoutingTable should resolve exact matches."""
    context = MockContext([
        {"agent": "cookie", "value": "telegram:123456"},
        {"agent": "pickle", "value": "telegram:.*"},
    ])
    table = RoutingTable(context)

    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_resolve_wildcard():
    """RoutingTable should fall back to wildcard patterns."""
    context = MockContext([
        {"agent": "cookie", "value": "telegram:123456"},
        {"agent": "pickle", "value": "telegram:.*"},
    ])
    table = RoutingTable(context)

    assert table.resolve("telegram:789") == "pickle"


def test_routing_table_resolve_no_match():
    """RoutingTable should return None if no pattern matches."""
    context = MockContext([
        {"agent": "pickle", "value": "telegram:.*"},
    ])
    table = RoutingTable(context)

    assert table.resolve("discord:123") is None


def test_routing_table_tier_priority():
    """More specific patterns should take priority."""
    context = MockContext([
        {"agent": "pickle", "value": "telegram:.*"},       # tier 2
        {"agent": "cookie", "value": "telegram:123456"},   # tier 0
    ])
    table = RoutingTable(context)

    # tier 0 should win even though tier 2 is listed first
    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_order_within_tier():
    """Within same tier, first pattern in config wins."""
    context = MockContext([
        {"agent": "cookie", "value": "telegram:12.*"},
        {"agent": "pickle", "value": "telegram:1.*"},
    ])
    table = RoutingTable(context)

    # Both tier 2, first one wins
    assert table.resolve("telegram:123456") == "cookie"


def test_routing_table_caches_bindings():
    """RoutingTable should cache compiled bindings."""
    context = MockContext([
        {"agent": "pickle", "value": "telegram:.*"},
    ])
    table = RoutingTable(context)

    # First call builds cache
    table.resolve("telegram:123")
    hash1 = table._config_hash

    # Second call uses cache
    table.resolve("telegram:456")
    assert table._config_hash == hash1


def test_routing_table_rebuilds_on_config_change():
    """RoutingTable should rebuild when config changes."""
    context = MockContext([
        {"agent": "pickle", "value": "telegram:.*"},
    ])
    table = RoutingTable(context)

    table.resolve("telegram:123")
    old_bindings = table._bindings

    # Change config
    context.config.routing["bindings"] = [
        {"agent": "cookie", "value": "telegram:.*"}
    ]

    # Should rebuild
    table.resolve("telegram:123")
    assert table._bindings != old_bindings
    assert table.resolve("telegram:123") == "cookie"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_routing.py::test_routing_table -v`
Expected: FAIL - RoutingTable not defined

**Step 3: Add RoutingTable class**

```python
# src/picklebot/core/routing.py (append to existing)

@dataclass
class RoutingTable:
    """Routes sources to agents using regex bindings."""

    _context: "SharedContext"
    _bindings: list[Binding] | None = field(default=None, init=False)
    _config_hash: int | None = field(default=None, init=False)

    def _load_bindings(self) -> list[Binding]:
        """Load and sort bindings from config. Cached until config changes."""
        bindings_data = self._context.config.routing.get("bindings", [])
        current_hash = hash(tuple((b["agent"], b["value"]) for b in bindings_data))

        if self._bindings is not None and self._config_hash == current_hash:
            return self._bindings

        # Rebuild
        bindings = [
            Binding(agent=b["agent"], value=b["value"])
            for b in bindings_data
        ]
        # Sort by tier, then by original order (using id as proxy for order)
        bindings_with_order = [
            (Binding(agent=b["agent"], value=b["value"]), i)
            for i, b in enumerate(bindings_data)
        ]
        bindings_with_order.sort(key=lambda x: (x[0].tier, x[1]))
        self._bindings = [b for b, _ in bindings_with_order]
        self._config_hash = current_hash

        return self._bindings

    def resolve(self, source: str) -> str | None:
        """Return agent_id for source, or None if no match."""
        for binding in self._load_bindings():
            if binding.pattern.match(source):
                return binding.agent
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/routing.py tests/core/test_routing.py
git commit -m "feat(routing): add RoutingTable with cached binding resolution"
```

---

## Task 4: Initialize RoutingTable in SharedContext

**Files:**
- Modify: `src/picklebot/core/context.py`
- Test: `tests/core/test_context.py`

**Step 1: Write the failing test**

```python
# tests/core/test_context.py

def test_shared_context_has_routing_table(tmp_path, mock_config):
    """SharedContext should initialize RoutingTable."""
    from picklebot.core.context import SharedContext
    from picklebot.core.routing import RoutingTable

    ctx = SharedContext(mock_config)

    assert hasattr(ctx, "routing_table")
    assert isinstance(ctx.routing_table, RoutingTable)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_context.py::test_shared_context_has_routing_table -v`
Expected: FAIL - routing_table not found

**Step 3: Add RoutingTable to SharedContext**

```python
# src/picklebot/core/context.py
# Add import at top:
from picklebot.core.routing import RoutingTable

# Add in __init__ method after other initializations:
        self.routing_table = RoutingTable(self)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context.py::test_shared_context_has_routing_table -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/context.py tests/core/test_context.py
git commit -m "feat(context): initialize RoutingTable in SharedContext"
```

---

## Task 5: Update MessageBusWorker - Remove Old Session Logic

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`
- Test: `tests/server/test_messagebus_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_messagebus_worker.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from picklebot.server.messagebus_worker import MessageBusWorker


@pytest.fixture
def mock_context():
    context = Mock()
    context.config = Mock()
    context.config.default_agent = "pickle"
    context.config.sources = {}
    context.config.messagebus = Mock()
    context.config.messagebus.enabled = True
    context.config.routing = {"bindings": [
        {"agent": "cookie", "value": "telegram:123456"},
        {"agent": "pickle", "value": "telegram:.*"},
    ]}

    context.routing_table = Mock()
    context.routing_table.resolve = Mock(return_value="cookie")

    context.agent_loader = Mock()
    context.agent_loader.load = Mock(return_value=Mock(id="cookie"))

    context.eventbus = Mock()
    context.eventbus.publish = AsyncMock()

    context.messagebus_buses = []
    context.command_registry = Mock()
    context.command_registry.dispatch = Mock(return_value=None)

    return context


def test_messagebus_worker_no_default_agent_in_init(mock_context):
    """MessageBusWorker should not pre-load default agent."""
    worker = MessageBusWorker(mock_context)

    assert not hasattr(worker, "agent_def")
    assert not hasattr(worker, "agent")


def test_get_or_create_session_uses_source_cache(mock_context):
    """_get_or_create_session_id should check source cache first."""
    mock_context.config.sources = {"telegram:123456": {"session_id": "existing-session"}}

    worker = MessageBusWorker(mock_context)
    session_id = worker._get_or_create_session_id("telegram:123456", "cookie")

    assert session_id == "existing-session"


def test_get_or_create_session_creates_new(mock_context):
    """_get_or_create_session_id should create session if not cached."""
    mock_context.config.set_runtime = Mock()
    mock_context.config.sources = {}

    with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
        mock_session = Mock(session_id="new-session-id")
        MockAgent.return_value.new_session.return_value = mock_session

        worker = MessageBusWorker(mock_context)
        session_id = worker._get_or_create_session_id("telegram:123456", "cookie")

        assert session_id == "new-session-id"
        mock_context.config.set_runtime.assert_called_once_with(
            "sources.telegram:123456",
            {"session_id": "new-session-id"}
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_messagebus_worker.py -v`
Expected: FAIL - _get_or_create_session_id doesn't exist yet or has wrong signature

**Step 3: Update MessageBusWorker**

```python
# src/picklebot/server/messagebus_worker.py

import asyncio
import time
from typing import TYPE_CHECKING, Any

from .worker import Worker
from picklebot.core.agent import Agent
from picklebot.core.events import InboundEvent, Source
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, publishes INBOUND events to EventBus."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

    def _get_or_create_session_id(self, source: str, agent_id: str) -> str:
        """Get existing session_id from source cache, or create new session."""
        # Check source cache
        source_info = self.context.config.sources.get(source)
        if source_info:
            return source_info["session_id"]

        # Create new session
        agent_def = self.context.agent_loader.load(agent_id)
        agent = Agent(agent_def, self.context)
        session = agent.new_session(source)

        # Update source cache
        self.context.config.set_runtime(
            f"sources.{source}",
            {"session_id": session.session_id}
        )
        return session.session_id

    async def run(self) -> None:
        """Start all buses and process incoming messages."""
        self.logger.info(f"MessageBusWorker started with {len(self.buses)} bus(es)")

        bus_tasks = [
            bus.run(self._create_callback(bus.platform_name)) for bus in self.buses
        ]

        try:
            await asyncio.gather(*bus_tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    def _create_callback(self, platform: str):
        """Create callback for a specific platform."""

        async def callback(message: str, context: Any) -> None:
            try:
                bus = self.bus_map[platform]

                if not bus.is_allowed(context):
                    self.logger.debug(
                        f"Ignored non-whitelisted message from {platform}"
                    )
                    return

                # Check for slash command
                if message.startswith("/"):
                    self.logger.debug(f"Processing slash command from {platform}")
                    result = self.context.command_registry.dispatch(
                        message, self.context
                    )
                    if result:
                        await bus.reply(result, context)
                    return

                # Build source and resolve agent
                user_id = context.user_id
                source = f"{platform}:{user_id}"
                agent_id = self.context.routing_table.resolve(source)

                if not agent_id:
                    self.logger.debug(f"No routing match for {source}")
                    return

                session_id = self._get_or_create_session_id(source, agent_id)

                # Publish INBOUND event
                event = InboundEvent(
                    session_id=session_id,
                    agent_id=agent_id,
                    source=source,
                    content=message,
                    timestamp=time.time(),
                    context=context,
                )
                await self.context.eventbus.publish(event)
                self.logger.debug(f"Published INBOUND event from {source}")

            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_messagebus_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/test_messagebus_worker.py
git commit -m "refactor(messagebus): use RoutingTable and source cache for inbound routing"
```

---

## Task 6: Update DeliveryWorker - Add LRU Cache and Simplify

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py`
- Test: `tests/server/test_delivery_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_delivery_worker.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from picklebot.server.delivery_worker import DeliveryWorker
from picklebot.core.events import OutboundEvent


@pytest.fixture
def mock_context():
    context = Mock()
    context.config = Mock()
    context.config.messagebus = Mock()

    context.history_store = Mock()
    context.eventbus = Mock()
    context.eventbus.subscribe = Mock()
    context.eventbus.ack = Mock()

    context.messagebus_buses = []

    return context


def test_delivery_worker_has_lru_cache(mock_context):
    """DeliveryWorker should use LRU cache for session lookup."""
    worker = DeliveryWorker(mock_context)

    # Check that _get_session_source is decorated with lru_cache
    assert hasattr(worker._get_session_source, "cache_info")


def test_get_session_source_returns_session(mock_context):
    """_get_session_source should return session with source."""
    from picklebot.core.history import HistorySession

    mock_session = HistorySession(
        id="session-123",
        agent_id="pickle",
        source="telegram:123456",
        created_at="2026-03-01T10:00:00",
        updated_at="2026-03-01T10:00:00",
    )
    mock_context.history_store.list_sessions.return_value = [mock_session]

    worker = DeliveryWorker(mock_context)
    result = worker._get_session_source("session-123")

    assert result == mock_session
    assert result.source == "telegram:123456"


def test_get_session_source_returns_none_if_not_found(mock_context):
    """_get_session_source should return None if session not found."""
    mock_context.history_store.list_sessions.return_value = []

    worker = DeliveryWorker(mock_context)
    result = worker._get_session_source("unknown-session")

    assert result is None


@pytest.mark.asyncio
async def test_handle_event_skips_if_no_source(mock_context):
    """handle_event should skip delivery if session has no source."""
    mock_context.history_store.list_sessions.return_value = []

    worker = DeliveryWorker(mock_context)
    event = OutboundEvent(
        session_id="unknown",
        agent_id="pickle",
        source="agent:pickle",
        content="Hello",
    )

    await worker.handle_event(event)

    # Should not ack since we skipped
    mock_context.eventbus.ack.assert_not_called()


@pytest.mark.asyncio
async def test_handle_event_delivers_to_platform(mock_context):
    """handle_event should deliver to platform from session source."""
    from picklebot.core.history import HistorySession
    from picklebot.messagebus.telegram_bus import TelegramContext

    mock_session = HistorySession(
        id="session-123",
        agent_id="pickle",
        source="telegram:123456",
        created_at="2026-03-01T10:00:00",
        updated_at="2026-03-01T10:00:00",
    )
    mock_context.history_store.list_sessions.return_value = [mock_session]

    mock_bus = Mock()
    mock_bus.platform_name = "telegram"
    mock_bus.reply = AsyncMock()
    mock_context.messagebus_buses = [mock_bus]

    worker = DeliveryWorker(mock_context)
    event = OutboundEvent(
        session_id="session-123",
        agent_id="pickle",
        source="agent:pickle",
        content="Hello",
    )

    await worker.handle_event(event)

    mock_bus.reply.assert_called_once()
    mock_context.eventbus.ack.assert_called_once_with(event)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_delivery_worker.py -v`
Expected: FAIL - methods don't exist or have wrong behavior

**Step 3: Update DeliveryWorker**

```python
# src/picklebot/server/delivery_worker.py

import logging
import random
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from picklebot.core.events import OutboundEvent, EventType
from picklebot.core.history import HistorySession
from .worker import SubscriberWorker

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)

# Retry configuration
BACKOFF_MS = [5000, 25000, 120000, 600000]  # 5s, 25s, 2min, 10min
MAX_RETRIES = 5

# Platform message size limits
PLATFORM_LIMITS: dict[str, float] = {
    "telegram": 4096,
    "discord": 2000,
    "cli": float("inf"),
}


def compute_backoff_ms(retry_count: int) -> int:
    """Compute backoff time with jitter."""
    if retry_count <= 0:
        return 0
    idx = min(retry_count - 1, len(BACKOFF_MS) - 1)
    base = BACKOFF_MS[idx]
    jitter = random.randint(-base // 5, base // 5)
    return max(0, base + jitter)


def chunk_message(content: str, limit: int) -> list[str]:
    """Split message at paragraph boundaries, respecting limit."""
    if len(content) <= limit:
        return [content]

    chunks = []
    paragraphs = content.split("\n\n")
    current = ""

    for para in paragraphs:
        if current:
            potential = current + "\n\n" + para
        else:
            potential = para

        if len(potential) <= limit:
            current = potential
        else:
            if current:
                chunks.append(current)

            if len(para) > limit:
                for i in range(0, len(para), limit):
                    chunks.append(para[i : i + limit])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


class DeliveryWorker(SubscriberWorker):
    """Worker that delivers outbound messages to platforms."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.context.eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
        self.logger.info("DeliveryWorker subscribed to OUTBOUND events")

    @lru_cache(maxsize=10)
    def _get_session_source(self, session_id: str) -> HistorySession | None:
        """Get session info from HistoryStore (cached)."""
        for session in self.context.history_store.list_sessions():
            if session.id == session_id:
                return session
        return None

    async def handle_event(self, event: OutboundEvent) -> None:
        """Handle an outbound message event."""
        try:
            session_info = self._get_session_source(event.session_id)

            if not session_info or not session_info.source:
                self.logger.warning(
                    f"No source for session {event.session_id}, skipping delivery"
                )
                return

            platform, user_id = session_info.source.split(":", 1)
            context = self._build_context(platform, user_id, session_info)

            limit = PLATFORM_LIMITS.get(platform, float("inf"))
            if limit != float("inf"):
                limit = int(limit)
            chunks = chunk_message(
                event.content,
                int(limit) if limit != float("inf") else len(event.content),
            )

            bus = self._get_bus(platform)
            if bus:
                for chunk in chunks:
                    await bus.reply(chunk, context)

            self.context.eventbus.ack(event)
            self.logger.info(
                f"Delivered message to {platform} for session {event.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")

    def _build_context(
        self, platform: str, user_id: str, session_info: HistorySession
    ) -> Any:
        """Rebuild platform context from stored session info."""
        if platform == "telegram":
            from picklebot.messagebus.telegram_bus import TelegramContext

            return TelegramContext(user_id=user_id, chat_id=user_id)
        elif platform == "discord":
            from picklebot.messagebus.discord_bus import DiscordContext

            stored = session_info.context or {}
            return DiscordContext(
                user_id=user_id, channel_id=stored.get("channel_id", user_id)
            )
        else:
            raise ValueError(f"Unknown platform: {platform}")

    def _get_bus(self, platform: str) -> "MessageBus[Any] | None":
        """Get the message bus for a platform."""
        for bus in self.context.messagebus_buses:
            if bus.platform_name == platform:
                return bus
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_delivery_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/delivery_worker.py tests/server/test_delivery_worker.py
git commit -m "refactor(delivery): simplify with LRU cache, remove proactive fallback"
```

---

## Task 7: Update Config Models - Remove Old Platform Fields

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_config.py (append to existing)

def test_telegram_config_no_sessions_field():
    """TelegramConfig should not have sessions field."""
    from picklebot.utils.config import TelegramConfig

    config = TelegramConfig(bot_token="test")
    assert not hasattr(config, "sessions")


def test_telegram_config_no_default_chat_id():
    """TelegramConfig should not have default_chat_id field."""
    from picklebot.utils.config import TelegramConfig

    config = TelegramConfig(bot_token="test")
    assert not hasattr(config, "default_chat_id")


def test_discord_config_no_sessions_field():
    """DiscordConfig should not have sessions field."""
    from picklebot.utils.config import DiscordConfig

    config = DiscordConfig(bot_token="test")
    assert not hasattr(config, "sessions")


def test_discord_config_no_default_chat_id():
    """DiscordConfig should not have default_chat_id field."""
    from picklebot.utils.config import DiscordConfig

    config = DiscordConfig(bot_token="test")
    assert not hasattr(config, "default_chat_id")


def test_messagebus_config_no_default_platform():
    """MessageBusConfig should not have default_platform field."""
    from picklebot.utils.config import MessageBusConfig

    config = MessageBusConfig()
    assert not hasattr(config, "default_platform")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py -v -k "no_sessions or no_default"
Expected: FAIL - fields still exist

**Step 3: Remove old fields from config**

```python
# src/picklebot/utils/config.py

# Update TelegramConfig:
class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)


# Update DiscordConfig:
class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)


# Update MessageBusConfig:
class MessageBusConfig(BaseModel):
    """Message bus configuration."""

    enabled: bool = False
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None

    # Remove the validate_default_platform validator
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py -v -k "no_sessions or no_default"
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "refactor(config): remove sessions and default_chat_id from platform configs"
```

---

## Task 8: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Fix any issues**

If tests fail or lint errors, fix them before proceeding.

---

## Task 9: Final Commit and Summary

**Step 1: Verify all changes**

Run: `git status`
Expected: Clean working tree

**Step 2: Push to remote**

```bash
git push origin main
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add routing/sources fields to Config |
| 2 | Create Binding dataclass |
| 3 | Create RoutingTable class |
| 4 | Initialize RoutingTable in SharedContext |
| 5 | Update MessageBusWorker |
| 6 | Update DeliveryWorker |
| 7 | Remove old config fields |
| 8 | Run tests and lint |
| 9 | Push changes |
