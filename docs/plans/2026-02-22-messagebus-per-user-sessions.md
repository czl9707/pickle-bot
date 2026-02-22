# MessageBus Per-User Sessions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Each user on each platform gets their own session that persists across service restarts.

**Architecture:** Session IDs stored in `config.runtime.yaml` under `messagebus.{platform}.sessions.{user_id}`. MessageBusWorker does lazy lookup per message, creating new sessions as needed. AgentWorker handles recovery when session exists in config but not in history.

**Tech Stack:** Pydantic config models, asyncio queues, UUID session IDs

---

### Task 1: Add sessions field to platform configs

**Files:**
- Modify: `src/picklebot/utils/config.py:31-48`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py` in `TestPlatformConfig` class:

```python
@pytest.mark.parametrize("config_class", [TelegramConfig, DiscordConfig])
def test_platform_config_has_sessions_field(config_class):
    """Platform configs should have sessions field for storing user session IDs."""
    config = config_class(enabled=True, bot_token="test-token")
    assert config.sessions == {}

    config_with_sessions = config_class(
        enabled=True,
        bot_token="test-token",
        sessions={"123456": "uuid-abc-123"}
    )
    assert config_with_sessions.sessions == {"123456": "uuid-abc-123"}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestPlatformConfig::test_platform_config_has_sessions_field -v`

Expected: FAIL with `pydantic.ValidationError: Extra inputs are not permitted` or `AttributeError`

**Step 3: Add sessions field to TelegramConfig and DiscordConfig**

Modify `src/picklebot/utils/config.py`:

```python
class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None
    sessions: dict[str, str] = Field(default_factory=dict)  # user_id -> session_id


class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None
    sessions: dict[str, str] = Field(default_factory=dict)  # user_id -> session_id
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestPlatformConfig::test_platform_config_has_sessions_field -v`

Expected: PASS

**Step 5: Run all config tests**

Run: `uv run pytest tests/utils/test_config.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add sessions field to TelegramConfig and DiscordConfig"
```

---

### Task 2: Add optional session_id parameter to new_session()

**Files:**
- Modify: `src/picklebot/core/agent.py:81-113`
- Test: `tests/core/test_agent.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
def test_agent_new_session_with_custom_session_id(test_agent):
    """Agent.new_session should accept optional session_id parameter."""
    custom_id = "custom-session-123"
    session = test_agent.new_session(SessionMode.CHAT, session_id=custom_id)

    assert session.session_id == custom_id
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_agent_new_session_with_custom_session_id -v`

Expected: FAIL with `TypeError: new_session() got an unexpected keyword argument 'session_id'`

**Step 3: Modify new_session() to accept optional session_id**

Modify `src/picklebot/core/agent.py`:

```python
def new_session(self, mode: SessionMode, session_id: str | None = None) -> "AgentSession":
    """
    Create a new conversation session.

    Args:
        mode: Session mode (CHAT or JOB)
        session_id: Optional session_id to use (for recovery scenarios)

    Returns:
        A new Session instance with mode-appropriate tools.
    """
    session_id = session_id or str(uuid.uuid4())

    # Determine max_history based on mode
    if mode == SessionMode.CHAT:
        max_history = self.context.config.chat_max_history
    else:
        max_history = self.context.config.job_max_history

    tools = self._build_tools(mode)

    session = AgentSession(
        session_id=session_id,
        agent_id=self.agent_def.id,
        context=self.context,
        agent=self,
        tools=tools,
        mode=mode,
        max_history=max_history,
    )

    self.context.history_store.create_session(self.agent_def.id, session_id)
    return session
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py::test_agent_new_session_with_custom_session_id -v`

Expected: PASS

**Step 5: Run all agent tests**

Run: `uv run pytest tests/core/test_agent.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "feat(agent): add optional session_id parameter to new_session()"
```

---

### Task 3: Update AgentWorker with session recovery fallback

**Files:**
- Modify: `src/picklebot/server/agent_worker.py:30-53`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

Add to `tests/server/test_agent_worker.py`:

```python
@pytest.mark.anyio
async def test_agent_worker_recovers_missing_session(test_context, tmp_path):
    """AgentWorker creates new session with same ID if session not found in history."""
    # Create a test agent definition
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

    # Create a job with a session_id that doesn't exist in history
    nonexistent_session_id = "nonexistent-session-uuid"
    job = Job(
        session_id=nonexistent_session_id,
        agent_id="test-agent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    await worker._process_job(job)

    # Session should be created with the provided ID
    assert job.session_id == nonexistent_session_id
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py::test_agent_worker_recovers_missing_session -v`

Expected: FAIL with `ValueError: Session not found`

**Step 3: Modify _process_job to handle missing session**

Modify `src/picklebot/server/agent_worker.py`:

```python
async def _process_job(self, job: Job) -> None:
    """Execute a single job with crash recovery."""
    try:
        agent_def = self.context.agent_loader.load(job.agent_id)
        agent = Agent(agent_def, self.context)

        if job.session_id:
            try:
                session = agent.resume_session(job.session_id)
            except ValueError:
                # Session not found in history - create new with same ID
                self.logger.warning(f"Session {job.session_id} not found, creating new")
                session = agent.new_session(job.mode, session_id=job.session_id)
        else:
            session = agent.new_session(job.mode)
            job.session_id = session.session_id

        await session.chat(job.message, job.frontend)

        self.logger.info(f"Job completed: session={job.session_id}")

    except DefNotFoundError as e:
        self.logger.error(f"Agent not found: {job.agent_id}: {e}")
    except Exception as e:
        self.logger.error(f"Job failed: {e}")

        job.message = "."
        await self.agent_queue.put(job)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py::test_agent_worker_recovers_missing_session -v`

Expected: PASS

**Step 5: Run all agent worker tests**

Run: `uv run pytest tests/server/test_agent_worker.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "fix(agent-worker): recover from missing session with same session_id"
```

---

### Task 4: Update MessageBusWorker for per-user sessions

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`
- Test: `tests/server/test_messagebus_worker.py`

**Step 1: Write the failing test for session lookup**

Add to `tests/server/test_messagebus_worker.py`:

```python
from dataclasses import dataclass
from picklebot.messagebus.base import MessageContext


@dataclass
class FakeContext(MessageContext):
    """Fake context with user_id for testing."""
    user_id: str
    chat_id: str


class FakeBusWithUser(FakeBus):
    """Fake bus that provides user_id in context."""

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message with user context
        await callback("hello", FakeContext(user_id="123", chat_id="456"))


@pytest.mark.anyio
async def test_messagebus_worker_creates_per_user_session(test_context, tmp_path):
    """MessageBusWorker creates a new session for each user."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    # Should NOT have global_session anymore
    assert not hasattr(worker, "global_session")

    # Should have agent for session creation
    assert worker.agent is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_messagebus_worker.py::test_messagebus_worker_creates_per_user_session -v`

Expected: FAIL with `AssertionError: assert hasattr(worker, 'global_session')` or AttributeError

**Step 3: Update MessageBusWorker**

Modify `src/picklebot/server/messagebus_worker.py`:

```python
"""MessageBus worker for ingesting platform messages."""

import asyncio
from typing import TYPE_CHECKING, Any

from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode, Agent
from picklebot.frontend.messagebus import MessageBusFrontend
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, dispatches to agent queue."""

    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

        # Load agent for session creation
        try:
            self.agent_def = context.agent_loader.load(context.config.default_agent)
            self.agent = Agent(self.agent_def, context)
        except DefNotFoundError as e:
            self.logger.error(
                f"Default agent not found: {context.config.default_agent}"
            )
            raise RuntimeError(f"Failed to initialize MessageBusWorker: {e}") from e

    def _get_or_create_session_id(self, platform: str, user_id: str) -> str:
        """Get existing session_id or create new session for this user."""
        platform_config = getattr(self.context.config.messagebus, platform, None)
        if not platform_config:
            raise ValueError(f"No config for platform: {platform}")

        session_id = platform_config.sessions.get(user_id)

        if session_id:
            return session_id

        # No session - create new (creates in HistoryStore)
        session = self.agent.new_session(SessionMode.CHAT)

        # Persist session_id to runtime config
        self.context.config.set_runtime(
            f"messagebus.{platform}.sessions.{user_id}",
            session.session_id
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

                # Extract user_id from context
                user_id = context.user_id

                # Get or create session for this user
                session_id = self._get_or_create_session_id(platform, user_id)

                frontend = MessageBusFrontend(bus, context)

                job = Job(
                    session_id=session_id,
                    agent_id=self.agent_def.id,
                    message=message,
                    frontend=frontend,
                    mode=SessionMode.CHAT,
                )
                await self.agent_queue.put(job)
                self.logger.debug(f"Dispatched message from {platform}")
            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_messagebus_worker.py::test_messagebus_worker_creates_per_user_session -v`

Expected: PASS

**Step 5: Update existing tests to use new structure**

Modify `tests/server/test_messagebus_worker.py` - update the existing tests that reference `global_session`:

```python
@pytest.mark.anyio
async def test_messagebus_worker_dispatches_to_queue(test_context, tmp_path):
    """MessageBusWorker dispatches incoming messages to agent queue."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    # Start worker (it will process one message and wait)
    task = asyncio.create_task(worker.run())

    # Wait for message to be dispatched
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check queue has job
    assert not queue.empty()
    job = await queue.get()
    assert job.message == "hello"
    assert job.session_id is not None  # Session ID assigned per user
```

Also delete the old `test_messagebus_worker_creates_global_session` test since it's no longer relevant.

**Step 6: Run all messagebus worker tests**

Run: `uv run pytest tests/server/test_messagebus_worker.py -v`

Expected: All tests pass

**Step 7: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/test_messagebus_worker.py
git commit -m "feat(messagebus): per-user session management with persistence"
```

---

### Task 5: Add test for session persistence across restart

**Files:**
- Test: `tests/server/test_messagebus_worker.py`

**Step 1: Write test for session persistence**

Add to `tests/server/test_messagebus_worker.py`:

```python
@pytest.mark.anyio
async def test_messagebus_worker_reuses_existing_session(test_context, tmp_path):
    """MessageBusWorker reuses session from config for returning users."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    # Pre-configure a session for user "123"
    from picklebot.utils.config import TelegramConfig, MessageBusConfig
    test_context.config.messagebus = MessageBusConfig(
        enabled=True,
        default_platform="fake",
        telegram=TelegramConfig(
            bot_token="test",
            sessions={"123": "existing-session-uuid"}
        )
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    # Start worker
    task = asyncio.create_task(worker.run())

    # Wait for message to be dispatched
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check queue has job with the existing session_id
    assert not queue.empty()
    job = await queue.get()
    assert job.session_id == "existing-session-uuid"
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_messagebus_worker.py::test_messagebus_worker_reuses_existing_session -v`

Expected: PASS

**Step 3: Commit**

```bash
git add tests/server/test_messagebus_worker.py
git commit -m "test(messagebus): verify session persistence for returning users"
```

---

### Task 6: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`

Expected: All tests pass

**Step 2: Run lint and format**

Run: `uv run black . && uv run ruff check .`

Expected: No errors

**Step 3: Final commit if any formatting changes**

```bash
git add -A
git commit -m "style: format code after implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add sessions field to platform configs | config.py, test_config.py |
| 2 | Add optional session_id to new_session() | agent.py, test_agent.py |
| 3 | Add session recovery fallback to AgentWorker | agent_worker.py, test_agent_worker.py |
| 4 | Update MessageBusWorker for per-user sessions | messagebus_worker.py, test_messagebus_worker.py |
| 5 | Test session persistence | test_messagebus_worker.py |
| 6 | Full test suite and lint | - |
