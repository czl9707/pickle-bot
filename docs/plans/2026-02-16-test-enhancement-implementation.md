# Test Suite Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create shared test fixtures and consolidate redundant tests to improve maintainability.

**Architecture:** Add `tests/conftest.py` with shared fixtures for Config, SharedContext, AgentDef, and Agent. Update 8 test files to use these fixtures. Consolidate 15 path tests into 6 focused tests.

**Tech Stack:** pytest, pydantic, pathlib

---

## Task 1: Create Shared Fixtures in conftest.py

**Files:**
- Create: `tests/conftest.py`

**Step 1: Create conftest.py with all shared fixtures**

```python
"""Shared test fixtures for picklebot test suite."""

from pathlib import Path

import pytest

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def llm_config() -> LLMConfig:
    """Minimal LLM config for testing."""
    return LLMConfig(provider="test", model="test-model", api_key="test-key")


@pytest.fixture
def test_config(tmp_path: Path, llm_config: LLMConfig) -> Config:
    """Config with workspace pointing to tmp_path."""
    return Config(workspace=tmp_path, llm=llm_config, default_agent="test")


@pytest.fixture
def test_context(test_config: Config) -> SharedContext:
    """SharedContext with test config."""
    return SharedContext(config=test_config)


@pytest.fixture
def test_agent_def(llm_config: LLMConfig) -> AgentDef:
    """Minimal AgentDef for testing."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        system_prompt="You are a test assistant.",
        llm=llm_config,
        behavior=AgentBehaviorConfig(),
    )


@pytest.fixture
def test_agent(test_context: SharedContext, test_agent_def: AgentDef) -> Agent:
    """Agent instance for testing."""
    return Agent(agent_def=test_agent_def, context=test_context)
```

**Step 2: Run tests to verify fixtures work**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All existing tests still pass (fixtures are just defined, not used yet)

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared fixtures in conftest.py"
```

---

## Task 2: Update test_context.py to Use Shared Fixtures

**Files:**
- Modify: `tests/core/test_context.py`

**Step 1: Simplify test to use fixtures**

Replace entire file with:

```python
"""Tests for SharedContext."""


def test_shared_context_holds_config_and_history_store(test_context):
    """SharedContext should hold config and history_store."""
    assert test_context.config is not None
    assert test_context.history_store is not None
    assert test_context.agent_loader is not None
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/test_context.py
git commit -m "refactor(test): use shared fixtures in test_context.py"
```

---

## Task 3: Update test_agent.py to Use Shared Fixtures

**Files:**
- Modify: `tests/core/test_agent.py`

**Step 1: Refactor to use shared fixtures**

Replace entire file with:

```python
"""Tests for the Agent class."""

from pathlib import Path

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


def test_agent_creation_with_new_structure(test_agent, test_agent_def, test_context):
    """Agent should be created with agent_def, llm, tools, context."""
    assert test_agent.agent_def is test_agent_def
    assert test_agent.context is test_context


def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference."""
    session = test_agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == test_agent_def.id
    assert session.agent is test_agent


def test_agent_registers_skill_tool_when_allowed(test_config):
    """Agent should register skill tool when allow_skills is True and skills exist."""
    # Create skills directory
    skills_path = test_config.skills_path
    skills_path.mkdir(parents=True, exist_ok=True)

    # Create a test skill
    test_skill_dir = skills_path / "test-skill"
    test_skill_dir.mkdir()
    skill_file = test_skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: Test Skill
description: A test skill
---

Test skill content.
"""
    )

    # Create agent with allow_skills=True
    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=True,
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names


def test_agent_skips_skill_tool_when_not_allowed(test_config):
    """Agent should NOT register skill tool when allow_skills is False."""
    # Create skills directory
    skills_path = test_config.skills_path
    skills_path.mkdir(parents=True, exist_ok=True)

    # Create a test skill (but it shouldn't be loaded)
    test_skill_dir = skills_path / "test-skill"
    test_skill_dir.mkdir()
    skill_file = test_skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: Test Skill
description: A test skill
---

Test skill content.
"""
    )

    # Create agent with allow_skills=False (default)
    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="test", model="test-model", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=False,
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names


def test_agent_registers_subagent_dispatch_tool(test_config, test_agent_def):
    """Agent should always register subagent_dispatch tool when other agents exist."""
    # Create another agent (so dispatch tool has something to dispatch to)
    other_agent_dir = test_config.agents_path / "other-agent"
    other_agent_dir.mkdir(parents=True)
    other_agent_file = other_agent_dir / "AGENT.md"
    other_agent_file.write_text("""---
name: Other Agent
description: Another agent for testing
---

You are another agent.
""")

    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names


def test_agent_skips_subagent_dispatch_when_no_other_agents(test_config, test_agent_def):
    """Agent should NOT register subagent_dispatch tool when no other agents exist."""
    # Don't create any other agents
    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_agent.py
git commit -m "refactor(test): use shared fixtures in test_agent.py"
```

---

## Task 4: Update test_session.py to Use Shared Fixtures

**Files:**
- Modify: `tests/core/test_session.py`

**Step 1: Refactor to use test_agent fixture**

Replace entire file with:

```python
"""Tests for AgentSession."""


def test_session_creation(test_agent):
    """Session should be created with required fields including agent."""
    session = test_agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == test_agent.agent_def.id
    assert session.agent is test_agent
    assert session.messages == []


def test_session_add_message(test_agent):
    """Session should add message to in-memory list and persist to history."""
    session = test_agent.new_session()

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = test_agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(test_agent):
    """Session should limit history to max_messages."""
    session = test_agent.new_session()

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_session.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_session.py
git commit -m "refactor(test): use shared fixtures in test_session.py"
```

---

## Task 5: Update test_messagebus_executor.py to Use Shared Fixtures

**Files:**
- Modify: `tests/core/test_messagebus_executor.py`

**Step 1: Refactor to use test_config fixture**

Replace entire file with:

```python
"""Tests for MessageBusExecutor."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from picklebot.core.context import SharedContext
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
def executor_with_mock_bus(test_config):
    """Create MessageBusExecutor with mock bus."""
    # Create test agent for the executor
    agents_path = test_config.agents_path
    test_agent_dir = agents_path / "test-agent"
    test_agent_dir.mkdir(parents=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    context = SharedContext(test_config)
    bus = MockBus("mock")
    executor = MessageBusExecutor(context, [bus])
    return executor, bus


@pytest.mark.anyio
async def test_messagebus_executor_enqueue_message(executor_with_mock_bus):
    """Test that messages are enqueued."""
    executor, _ = executor_with_mock_bus

    await executor._enqueue_message("Hello", "mock", "user123")

    assert executor.message_queue.qsize() == 1


@pytest.mark.anyio
async def test_messagebus_executor_processes_queue(executor_with_mock_bus):
    """Test that messages are processed from queue."""
    executor, bus = executor_with_mock_bus

    # Mock the session.chat method to avoid LLM calls
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test response"

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
        assert bus.messages_sent[0] == ("user123", "Test response")


@pytest.mark.anyio
async def test_messagebus_executor_handles_errors(executor_with_mock_bus):
    """Test that errors during processing are handled gracefully."""
    executor, bus = executor_with_mock_bus

    # Mock session.chat to raise an error
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.side_effect = Exception("LLM error")

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

        # Verify error message was sent
        assert len(bus.messages_sent) > 0
        assert "error" in bus.messages_sent[0][1].lower()


@pytest.mark.anyio
async def test_messagebus_executor_multiple_platforms(test_config):
    """Test that executor works with multiple platforms."""
    # Create test agent
    agents_path = test_config.agents_path
    test_agent_dir = agents_path / "test-agent"
    test_agent_dir.mkdir(parents=True)
    agent_file = test_agent_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    context = SharedContext(test_config)

    bus1 = MockBus("telegram")
    bus2 = MockBus("discord")
    executor = MessageBusExecutor(context, [bus1, bus2])

    # Mock the session.chat method
    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test response"

        # Enqueue messages for different platforms
        await executor._enqueue_message("Hello Telegram", "telegram", "user1")
        await executor._enqueue_message("Hello Discord", "discord", "user2")

        # Start processing
        task = asyncio.create_task(executor._process_messages())

        # Wait for messages to be processed
        await asyncio.sleep(0.5)

        # Stop the worker
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify messages were sent to correct platforms
        assert len(bus1.messages_sent) == 1
        assert bus1.messages_sent[0] == ("user1", "Test response")
        assert len(bus2.messages_sent) == 1
        assert bus2.messages_sent[0] == ("user2", "Test response")
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_messagebus_executor.py
git commit -m "refactor(test): use shared fixtures in test_messagebus_executor.py"
```

---

## Task 6: Update test_subagent_tool.py to Use Shared Fixtures

**Files:**
- Modify: `tests/tools/test_subagent_tool.py`

**Step 1: Refactor to use test_config fixture**

Replace entire file with:

```python
"""Tests for subagent dispatch tool factory."""

import json
from unittest.mock import ANY, AsyncMock, patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool


class TestCreateSubagentDispatchTool:
    """Tests for create_subagent_dispatch_tool factory function."""

    def test_create_tool_returns_none_when_no_agents(self, test_config):
        """create_subagent_dispatch_tool should return None when no agents available."""
        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("any-agent", context)
        assert tool_func is None

    def test_tool_has_correct_schema(self, test_config):
        """Subagent dispatch tool should have correct name, description, and parameters."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("reviewer", "Code Reviewer", "Reviews code for quality"),
            ("planner", "Task Planner", "Plans and organizes tasks"),
        ]:
            agent_dir = test_config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)

        assert tool_func is not None
        # Check tool properties
        assert tool_func.name == "subagent_dispatch"
        assert "Dispatch a task to a specialized subagent" in tool_func.description
        assert "<available_agents>" in tool_func.description
        assert 'id="reviewer"' in tool_func.description
        assert "Reviews code for quality" in tool_func.description
        assert 'id="planner"' in tool_func.description

        # Check parameters schema
        params = tool_func.parameters
        assert params["type"] == "object"
        assert "agent_id" in params["properties"]
        assert params["properties"]["agent_id"]["type"] == "string"
        assert set(params["properties"]["agent_id"]["enum"]) == {"reviewer", "planner"}
        assert "task" in params["properties"]
        assert "context" in params["properties"]
        assert params["required"] == ["agent_id", "task"]

    def test_tool_excludes_calling_agent(self, test_config):
        """Subagent dispatch tool should exclude the calling agent from enum."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-a", "Agent A", "First agent"),
            ("agent-b", "Agent B", "Second agent"),
            ("agent-c", "Agent C", "Third agent"),
        ]:
            agent_dir = test_config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=test_config)

        # When agent-b calls the factory, it should be excluded
        tool_func = create_subagent_dispatch_tool("agent-b", context)

        assert tool_func is not None
        enum_ids = set(tool_func.parameters["properties"]["agent_id"]["enum"])
        assert "agent-a" in enum_ids
        assert "agent-c" in enum_ids
        assert "agent-b" not in enum_ids  # Excluded!

    @pytest.mark.anyio
    async def test_tool_dispatches_to_subagent(self, test_config):
        """Subagent dispatch tool should create session and return result + session_id."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text("""---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
""")

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        # Simpler approach: mock Agent and Session
        mock_response = "Task completed successfully"

        with patch("picklebot.core.agent.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-123"
            mock_session.chat = AsyncMock(return_value=mock_response)

            # Execute
            result = await tool_func.execute(
                agent_id="target-agent", task="Do something"
            )

            # Verify
            parsed = json.loads(result)
            assert parsed["result"] == "Task completed successfully"
            assert parsed["session_id"] == "test-session-123"

            # Verify session.chat was called with correct message
            mock_session.chat.assert_called_once_with("Do something", ANY)

    @pytest.mark.anyio
    async def test_tool_includes_context_in_message(self, test_config):
        """Subagent dispatch tool should include context in user message."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text("""---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
""")

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        with patch("picklebot.core.agent.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-456"
            mock_session.chat = AsyncMock(return_value="Done")

            # Execute with context
            await tool_func.execute(
                agent_id="target-agent",
                task="Review this",
                context="The code is in src/main.py",
            )

            # Verify context was included
            mock_session.chat.assert_called_once()
            call_args = mock_session.chat.call_args
            message = call_args[0][0]
            assert "Review this" in message
            assert "Context:" in message
            assert "The code is in src/main.py" in message
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/tools/test_subagent_tool.py
git commit -m "refactor(test): use shared fixtures in test_subagent_tool.py"
```

---

## Task 7: Update test_server.py to Use Shared Fixtures

**Files:**
- Modify: `tests/cli/test_server.py`

**Step 1: Refactor to use test_config fixture**

Replace entire file with:

```python
"""Tests for server CLI command."""

from unittest.mock import AsyncMock, patch

import pytest

from picklebot.cli.server import _run_server
from picklebot.core.context import SharedContext
from picklebot.utils.config import MessageBusConfig, TelegramConfig


class TestRunServer:
    """Test _run_server async function."""

    @pytest.mark.asyncio
    async def test_starts_cron_executor_when_messagebus_disabled(self, test_config):
        """Start CronExecutor when messagebus is disabled."""
        with patch("picklebot.cli.server.CronExecutor") as mock_cron_executor:
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            context = SharedContext(test_config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_starts_messagebus_executor_when_enabled(self, test_config):
        """Start MessageBusExecutor when messagebus is enabled."""
        test_config.messagebus = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=True, bot_token="test"),
        )

        with (
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
        ):
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            mock_bus = AsyncMock()
            mock_bus_executor.return_value = mock_bus
            mock_bus.run = AsyncMock()

            context = SharedContext(test_config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)
            mock_bus_executor.assert_called_once_with(context, context.messagebus_buses)

    @pytest.mark.asyncio
    async def test_does_not_start_messagebus_when_no_buses(self, test_config):
        """Don't start MessageBusExecutor if no buses are configured."""
        test_config.messagebus = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=False, bot_token="test"),
        )

        with (
            patch("picklebot.cli.server.CronExecutor") as mock_cron_executor,
            patch("picklebot.cli.server.MessageBusExecutor") as mock_bus_executor,
        ):
            mock_cron = AsyncMock()
            mock_cron_executor.return_value = mock_cron
            mock_cron.run = AsyncMock()

            context = SharedContext(test_config)
            await _run_server(context)

            mock_cron_executor.assert_called_once_with(context)
            mock_bus_executor.assert_not_called()
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_server.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/cli/test_server.py
git commit -m "refactor(test): use shared fixtures in test_server.py"
```

---

## Task 8: Update test_config_validation.py to Use Shared Fixture

**Files:**
- Modify: `tests/utils/test_config_validation.py`

**Step 1: Remove duplicate fixture, use shared llm_config**

Replace entire file with:

```python
"""Tests for config validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import (
    Config,
    MessageBusConfig,
    TelegramConfig,
    DiscordConfig,
)


def test_messagebus_disabled_by_default(llm_config):
    """Test that messagebus is disabled by default."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="pickle",
    )
    assert not config.messagebus.enabled


def test_messagebus_enabled_requires_default_platform():
    """Test that enabled messagebus requires default_platform."""
    with pytest.raises(ValidationError, match="default_platform is required"):
        MessageBusConfig(enabled=True)


def test_messagebus_validates_platform_config():
    """Test that default_platform must have valid config."""
    with pytest.raises(ValidationError, match="telegram config is missing"):
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


def test_messagebus_validates_discord_platform():
    """Test that discord platform requires discord config."""
    with pytest.raises(ValidationError, match="discord config is missing"):
        MessageBusConfig(enabled=True, default_platform="discord")


def test_messagebus_valid_discord_config():
    """Test valid discord configuration."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="discord",
        discord=DiscordConfig(bot_token="test_token", channel_id="12345")
    )
    assert config.enabled
    assert config.default_platform == "discord"
    assert config.discord.channel_id == "12345"


def test_messagebus_validates_invalid_platform():
    """Test that invalid platform is rejected."""
    with pytest.raises(ValidationError, match="Invalid default_platform"):
        MessageBusConfig(enabled=True, default_platform="invalid")


def test_messagebus_can_be_disabled():
    """Test that messagebus can be explicitly disabled."""
    config = MessageBusConfig(enabled=False)
    assert not config.enabled


def test_messagebus_integration_with_config(llm_config):
    """Test messagebus integration with full config."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="pickle",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(bot_token="test_token")
        )
    )
    assert config.messagebus.enabled
    assert config.messagebus.default_platform == "telegram"
    assert config.messagebus.telegram.bot_token == "test_token"
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_config_validation.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/utils/test_config_validation.py
git commit -m "refactor(test): use shared llm_config fixture in test_config_validation.py"
```

---

## Task 9: Consolidate test_config.py

**Files:**
- Modify: `tests/utils/test_config.py`

**Step 1: Replace with consolidated tests**

Replace entire file with:

```python
"""Tests for config path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import Config


class TestPathResolution:
    """Tests for path resolution against workspace."""

    def test_resolves_all_relative_paths_against_workspace(self, llm_config):
        """All relative paths should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
        )
        assert config.agents_path == Path("/workspace/agents")
        assert config.skills_path == Path("/workspace/skills")
        assert config.crons_path == Path("/workspace/crons")
        assert config.logging_path == Path("/workspace/.logs")
        assert config.history_path == Path("/workspace/.history")
        assert config.memories_path == Path("/workspace/memories")

    def test_resolves_custom_relative_paths(self, llm_config):
        """Custom relative paths should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
            agents_path=Path("custom/agents"),
            skills_path=Path("custom/skills"),
        )
        assert config.agents_path == Path("/workspace/custom/agents")
        assert config.skills_path == Path("/workspace/custom/skills")

    def test_rejects_absolute_agents_path(self, llm_config):
        """Absolute agents_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
                default_agent="test",
                agents_path=Path("/etc/agents"),
            )
        assert "agents_path must be relative" in str(exc.value)


class TestConfigValidation:
    """Tests for config validation rules."""

    def test_default_agent_required(self, llm_config):
        """default_agent is required."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
            )
        assert "default_agent" in str(exc.value)
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: All PASS (4 tests now instead of 15)

**Step 3: Commit**

```bash
git add tests/utils/test_config.py
git commit -m "refactor(test): consolidate redundant path tests in test_config.py"
```

---

## Task 10: Final Verification

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass, fewer total tests due to consolidation

**Step 2: Check test count**

Run: `uv run pytest tests/ --collect-only | grep "test session starts" -A 100 | grep -E "<Module|<Function" | wc -l`
Expected: Reduced count (from ~85 to ~76 tests)

**Step 3: Final commit if any cleanup needed**

```bash
git status
# If any uncommitted changes:
git add -A
git commit -m "chore: final cleanup after test enhancement"
```

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Test files with duplicate config construction | 6+ | 0 |
| Tests in test_config.py | 15 | 4 |
| Shared fixtures | 0 | 5 |
| Total tests | ~85 | ~76 |
