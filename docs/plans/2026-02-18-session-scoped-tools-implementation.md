# Session-Scoped Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move tool registration from Agent.__init__() to new_session() so that post_message tool is only available in JOB mode.

**Architecture:** Each AgentSession owns its own ToolRegistry built at session creation time based on SessionMode. Agent becomes a factory that builds mode-appropriate toolsets.

**Tech Stack:** Python 3.12, pytest, dataclasses

---

### Task 1: Update AgentSession to own tools and mode

**Files:**
- Modify: `src/picklebot/core/agent.py:144-156` (AgentSession dataclass)

**Step 1: Write the failing test**

Create `tests/core/test_session_tools.py`:

```python
"""Tests for session-scoped tool registration."""

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import LLMConfig, MessagebusConfig


def test_session_has_tools_attribute(test_agent):
    """Session should have a tools attribute."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert hasattr(session, "tools")
    assert session.tools is not None


def test_session_has_mode_attribute(test_agent):
    """Session should store its mode."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.mode == SessionMode.CHAT
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_session_tools.py -v`
Expected: FAIL with "AttributeError: 'AgentSession' object has no attribute 'tools'"

**Step 3: Add tools and mode fields to AgentSession**

Modify `src/picklebot/core/agent.py` at the AgentSession dataclass (around line 144):

```python
@dataclass
class AgentSession:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    context: SharedContext
    agent: Agent  # Reference to parent agent for LLM access
    tools: ToolRegistry  # Session's own tool registry
    mode: SessionMode  # Session mode (CHAT or JOB)
    max_history: int  # Max messages to include in LLM context

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
```

Also add the import for ToolRegistry at the top if not already present:
```python
from picklebot.tools.registry import ToolRegistry
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_session_tools.py::test_session_has_tools_attribute tests/core/test_session_tools.py::test_session_has_mode_attribute -v`
Expected: These tests will still fail because Agent.new_session() doesn't pass tools yet

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_session_tools.py
git commit -m "feat(session): add tools and mode fields to AgentSession"
```

---

### Task 2: Refactor Agent to build tools per session

**Files:**
- Modify: `src/picklebot/core/agent.py:45-108` (Agent class)

**Step 1: Write the failing test**

Add to `tests/core/test_session_tools.py`:

```python
def test_session_has_own_tool_registry(test_agent):
    """Session should have its own ToolRegistry instance."""
    session = test_agent.new_session(SessionMode.CHAT)

    # Session should have its own registry, not the agent's
    assert session.tools is not test_agent.tools
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_session_tools.py::test_session_has_own_tool_registry -v`
Expected: FAIL (session.tools doesn't exist yet / agent.tools still exists)

**Step 3: Refactor Agent class**

Replace the Agent class in `src/picklebot/core/agent.py`:

1. Remove `self.tools` from `__init__` and delete the `_register_*_tool` methods
2. Add `_build_tools(mode: SessionMode) -> ToolRegistry` method
3. Update `new_session()` to build tools and pass to session

```python
class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM and config
    that sessions use for chatting.
    """

    def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
        self.agent_def = agent_def
        self.context = context
        self.llm = LLMProvider.from_config(agent_def.llm)

    def _build_tools(self, mode: SessionMode) -> ToolRegistry:
        """
        Build a ToolRegistry with tools appropriate for the session mode.

        Args:
            mode: Session mode (CHAT or JOB)

        Returns:
            ToolRegistry with base tools + mode-appropriate optional tools
        """
        registry = ToolRegistry.with_builtins()

        # Register skill tool if allowed
        if self.agent_def.allow_skills:
            skill_tool = create_skill_tool(self.context.skill_loader)
            if skill_tool:
                registry.register(skill_tool)

        # Register subagent dispatch tool if other agents exist
        subagent_tool = create_subagent_dispatch_tool(
            self.agent_def.id, self.context
        )
        if subagent_tool:
            registry.register(subagent_tool)

        # Register post_message tool only in JOB mode
        if mode == SessionMode.JOB:
            post_tool = create_post_message_tool(self.context)
            if post_tool:
                registry.register(post_tool)

        return registry

    def new_session(self, mode: SessionMode) -> "AgentSession":
        """
        Create a new conversation session.

        Args:
            mode: Session mode (CHAT or JOB) determines history limit and tool availability

        Returns:
            A new Session instance with mode-appropriate tools.
        """
        session_id = str(uuid.uuid4())

        # Determine max_history based on mode
        if mode == SessionMode.CHAT:
            max_history = self.context.config.chat_max_history
        else:
            max_history = self.context.config.job_max_history

        # Build tools for this session
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

    def resume_session(self, session_id: str) -> "AgentSession":
        """
        Load an existing conversation session.

        Args:
            session_id: The ID of the session to load.

        Returns:
            A Session instance with self as the agent reference.
        """
        session_query = [
            session
            for session in self.context.history_store.list_sessions()
            if session.id == session_id
        ]
        if not session_query:
            raise ValueError(f"Session not found: {session_id}")

        session_info = session_query[0]
        history_messages = self.context.history_store.get_messages(session_id)

        # Convert HistoryMessage to litellm Message format
        messages: list[Message] = [msg.to_message() for msg in history_messages]

        # Build tools for resumed session (default to CHAT mode)
        tools = self._build_tools(SessionMode.CHAT)

        return AgentSession(
            session_id=session_info.id,
            agent_id=session_info.agent_id,
            context=self.context,
            agent=self,
            tools=tools,
            mode=SessionMode.CHAT,  # Default to CHAT mode for resumed sessions
            messages=messages,
            max_history=self.context.config.chat_max_history,
        )
```

**Step 4: Run tests to verify**

Run: `uv run pytest tests/core/test_agent.py tests/core/test_session.py tests/core/test_session_tools.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_session_tools.py
git commit -m "refactor(agent): move tool registration to session creation"
```

---

### Task 3: Update AgentSession.chat() to use session.tools

**Files:**
- Modify: `src/picklebot/core/agent.py:190-303` (AgentSession methods)

**Step 1: Update AgentSession.chat()**

In `src/picklebot/core/agent.py`, update the `AgentSession.chat()` method to use `self.tools` instead of `self.agent.tools`:

```python
async def chat(self, message: str, frontend: "Frontend") -> str:
    """
    Send a message to the LLM and get a response.

    Args:
        message: User message
        frontend: Frontend for displaying output

    Returns:
        Assistant's response text
    """
    user_msg: Message = {"role": "user", "content": message}
    self.add_message(user_msg)

    tool_schemas = self.tools.get_tool_schemas()  # Changed from self.agent.tools
    tool_count = 0
    display_content = "Thinking"

    while True:
        with frontend.show_transient(display_content):
            messages = self._build_messages()
            content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)

            tool_call_dicts: list[ChatCompletionMessageToolCallParam] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
            assistant_msg: Message = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_call_dicts,
            }

            self.add_message(assistant_msg)

            if not tool_calls:
                break

            await self._handle_tool_calls(tool_calls, content, frontend)
            tool_count += len(tool_calls)

            display_content = f"{content}\n - Total Tools Used: {tool_count}"

            continue

    return content
```

Also update `_execute_tool_call()` to use `self.tools`:

```python
async def _execute_tool_call(
    self,
    tool_call: "LLMToolCall",
    llm_content: str,
    frontend: "Frontend",
) -> str:
    """
    Execute a single tool call.

    Args:
        tool_call: Tool call from LLM response
        llm_content: LLM's text content alongside tool calls
        frontend: Frontend for displaying output

    Returns:
        Tool execution result
    """
    # Extract key arguments for display
    try:
        args = json.loads(tool_call.arguments)
    except json.JSONDecodeError:
        args = {}

    tool_display = f"Making Tool Call: {tool_call.name} {tool_call.arguments}"
    if len(tool_display) > 40:
        tool_display = tool_display[:40] + "..."

    with frontend.show_transient(tool_display):
        try:
            result = await self.tools.execute_tool(tool_call.name, **args)  # Changed from self.agent.tools
        except Exception as e:
            result = f"Error executing tool: {e}"

        return result
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/core/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "refactor(session): use session.tools instead of agent.tools"
```

---

### Task 4: Add test for post_message tool availability

**Files:**
- Modify: `tests/core/test_session_tools.py`

**Step 1: Write the test**

Add to `tests/core/test_session_tools.py`:

```python
import pytest
from pathlib import Path
from picklebot.utils.config import Config, MessagebusConfig, MessagebusPlatformConfig


def test_post_message_not_available_in_chat_mode(test_config):
    """post_message tool should NOT be available in CHAT mode."""
    # Enable messagebus to make post_message tool possible
    test_config.messagebus = MessagebusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=MessagebusPlatformConfig(
            enabled=True,
            bot_token="test-token",
            allowed_chat_ids=["123"],
            default_chat_id="123",
        ),
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "post_message" not in tool_names


def test_post_message_available_in_job_mode(test_config):
    """post_message tool should be available in JOB mode."""
    # Enable messagebus to make post_message tool possible
    test_config.messagebus = MessagebusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=MessagebusPlatformConfig(
            enabled=True,
            bot_token="test-token",
            allowed_chat_ids=["123"],
            default_chat_id="123",
        ),
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    session = agent.new_session(SessionMode.JOB)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "post_message" in tool_names
```

**Step 2: Check imports**

Add missing imports to `tests/core/test_session_tools.py`:

```python
"""Tests for session-scoped tool registration."""

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import LLMConfig, MessagebusConfig, MessagebusPlatformConfig
```

**Step 3: Run test to verify**

Run: `uv run pytest tests/core/test_session_tools.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/core/test_session_tools.py
git commit -m "test(session): verify post_message only available in JOB mode"
```

---

### Task 5: Update existing tests to use session.tools

**Files:**
- Modify: `tests/core/test_agent.py`

**Step 1: Update test_agent_registers_skill_tool_when_allowed**

The test currently checks `agent.tools`. It needs to check `session.tools` instead:

```python
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
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=True,
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names
```

**Step 2: Update test_agent_skips_skill_tool_when_not_allowed**

```python
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
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=False,
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is NOT registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names
```

**Step 3: Update test_agent_registers_subagent_dispatch_tool**

```python
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

    # Check that subagent_dispatch tool is registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names
```

**Step 4: Update test_agent_skips_subagent_dispatch_when_no_other_agents**

```python
def test_agent_skips_subagent_dispatch_when_no_other_agents(test_config, test_agent_def):
    """Agent should NOT register subagent_dispatch tool when no other agents exist."""
    # Don't create any other agents
    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names
```

**Step 5: Run all tests**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add tests/core/test_agent.py
git commit -m "test(agent): update tests to use session.tools"
```

---

### Task 6: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linter and type checker**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address linting and type errors"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Add tools and mode to AgentSession | `agent.py`, `test_session_tools.py` |
| 2 | Refactor Agent to build tools per session | `agent.py` |
| 3 | Update AgentSession.chat() to use session.tools | `agent.py` |
| 4 | Add tests for post_message availability | `test_session_tools.py` |
| 5 | Update existing tests | `test_agent.py` |
| 6 | Verify all tests pass | - |
