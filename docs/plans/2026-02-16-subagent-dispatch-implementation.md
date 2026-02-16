# Subagent Dispatch Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `subagent_dispatch` tool that enables agents to delegate specialized work to other pre-defined agents.

**Architecture:** Tool factory pattern (similar to skill tool) with dynamic schema. The factory creates a tool with an enum of dispatchable agents (excluding the calling agent). Each dispatch creates a new session that persists to history, and returns the result plus session ID as JSON.

**Tech Stack:** Python, Pydantic, pytest, asyncio

---

## Task 1: Add `description` field to AgentDef

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:23-31`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent_loader.py`:

```python
def test_load_agent_with_description(tmp_path):
    """AgentDef should include description from frontmatter."""
    # Setup
    agents_path = tmp_path / "agents"
    agent_dir = agents_path / "test-agent"
    agent_dir.mkdir(parents=True)
    agent_file = agent_dir / "AGENT.md"
    agent_file.write_text("""---
name: Test Agent
description: A test agent for unit testing
---

You are a test assistant.
""")
    # shared_llm = LLMConfig(...)

    from picklebot.utils.config import LLMConfig
    from picklebot.core.agent_loader import AgentLoader

    shared_llm = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")
    loader = AgentLoader(agents_path, shared_llm)

    # Execute
    agent_def = loader.load("test-agent")

    # Verify
    assert agent_def.description == "A test agent for unit testing"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_load_agent_with_description -v`
Expected: FAIL with ValidationError or "description" field issue

**Step 3: Write minimal implementation**

Modify `src/picklebot/core/agent_loader.py`:

```python
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    description: str  # Brief description for dispatch tool
    system_prompt: str
    llm: LLMConfig
    behavior: AgentBehaviorConfig
    allow_skills: bool = False
```

Update `_parse_agent_def` method to include description:

```python
def _parse_agent_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> AgentDef:
    """Parse agent definition from frontmatter (callback for parse_definition)."""
    merged_llm = self._merge_llm_config(frontmatter)

    try:
        return AgentDef(
            id=def_id,
            name=frontmatter.get("name"),
            description=frontmatter.get("description"),
            system_prompt=body.strip(),
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
            allow_skills=frontmatter.get("allow_skills", False),
        )
    except ValidationError as e:
        raise InvalidDefError("agent", def_id, str(e))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::test_load_agent_with_description -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(agent): add description field to AgentDef"
```

---

## Task 2: Add `discover_agents` method to AgentLoader

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent_loader.py`:

```python
def test_discover_agents_returns_all_agents(tmp_path):
    """discover_agents should return list of all valid AgentDef."""
    # Setup
    from picklebot.utils.config import LLMConfig
    from picklebot.core.agent_loader import AgentLoader

    agents_path = tmp_path / "agents"

    # Create multiple agents
    for agent_id, name, desc in [
        ("agent-one", "Agent One", "First test agent"),
        ("agent-two", "Agent Two", "Second test agent"),
    ]:
        agent_dir = agents_path / agent_id
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

    shared_llm = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")
    loader = AgentLoader(agents_path, shared_llm)

    # Execute
    agents = loader.discover_agents()

    # Verify
    assert len(agents) == 2
    agent_ids = {a.id for a in agents}
    assert "agent-one" in agent_ids
    assert "agent-two" in agent_ids
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_discover_agents_returns_all_agents -v`
Expected: FAIL with AttributeError "'AgentLoader' has no attribute 'discover_agents'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/core/agent_loader.py` after the `load` method:

```python
import logging

logger = logging.getLogger(__name__)

# ... in AgentLoader class ...

def discover_agents(self) -> list[AgentDef]:
    """Scan agents directory and return list of valid AgentDef.

    Returns:
        List of AgentDef objects for all valid agents
    """
    return discover_definitions(
        self.agents_path, "AGENT.md", self._parse_agent_def, logger
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::test_discover_agents_returns_all_agents -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(agent-loader): add discover_agents method"
```

---

## Task 3: Create subagent_tool.py with factory function

**Files:**
- Create: `src/picklebot/tools/subagent_tool.py`
- Test: `tests/tools/test_subagent_tool.py`

**Step 1: Write the failing test**

Create `tests/tools/test_subagent_tool.py`:

```python
"""Tests for subagent dispatch tool factory."""

import pytest
from pathlib import Path

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.context import SharedContext
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.utils.config import Config, LLMConfig


class TestCreateSubagentDispatchTool:
    """Tests for create_subagent_dispatch_tool factory function."""

    def test_create_tool_returns_none_when_no_agents(self, tmp_path: Path):
        """create_subagent_dispatch_tool should return None when no agents available."""
        config = self._create_test_config(tmp_path)
        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "any-agent", context)
        assert tool_func is None

    def _create_test_config(self, tmp_path: Path) -> Config:
        """Create a minimal test config."""
        config_file = tmp_path / "config.system.yaml"
        config_file.write_text("""
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
default_agent: test-agent
""")
        return Config.load(tmp_path)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: FAIL with ModuleNotFoundError "No module named 'picklebot.tools.subagent_tool'"

**Step 3: Write minimal implementation**

Create `src/picklebot/tools/subagent_tool.py`:

```python
"""Subagent dispatch tool factory for creating dynamic dispatch tool."""

import json
from typing import TYPE_CHECKING, Callable

from picklebot.core.agent import Agent
from picklebot.frontend.base import SilentFrontend
from picklebot.tools.base import tool
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.agent_loader import AgentLoader
    from picklebot.core.context import SharedContext


def create_subagent_dispatch_tool(
    agent_loader: "AgentLoader",
    current_agent_id: str,
    context: "SharedContext",
) -> Callable | None:
    """Factory to create subagent dispatch tool with dynamic schema.

    Args:
        agent_loader: AgentLoader instance for discovering and loading agents
        current_agent_id: ID of the calling agent (will be excluded from enum)
        context: SharedContext for creating subagents

    Returns:
        Async tool function for dispatching to subagents, or None if no agents available
    """
    # Discover available agents, exclude current
    available_agents = agent_loader.discover_agents()
    dispatchable_agents = [a for a in available_agents if a.id != current_agent_id]

    if not dispatchable_agents:
        return None

    # Build description listing available agents
    agents_desc = "<available_agents>\n"
    for agent_def in dispatchable_agents:
        agents_desc += f'  <agent id="{agent_def.id}">{agent_def.description}</agent>\n'
    agents_desc += "</available_agents>"

    # Build enum of dispatchable agent IDs
    dispatchable_ids = [a.id for a in dispatchable_agents]

    @tool(
        name="subagent_dispatch",
        description=f"Dispatch a task to a specialized subagent.\n{agents_desc}",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "enum": dispatchable_ids,
                    "description": "ID of the agent to dispatch to",
                },
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to perform",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context information for the subagent",
                },
            },
            "required": ["agent_id", "task"],
        },
    )
    async def subagent_dispatch(agent_id: str, task: str, context: str = "") -> str:
        """Dispatch task to subagent, return result + session_id."""
        # Load target agent definition
        try:
            target_def = agent_loader.load(agent_id)
        except DefNotFoundError:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Create subagent instance
        subagent = Agent(target_def, context)

        # Build initial message
        user_message = task
        if context:
            user_message = f"{task}\n\nContext:\n{context}"

        # Create new session and run with silent frontend
        session = subagent.new_session()
        response = await session.chat(user_message, SilentFrontend())

        # Return result + session_id as JSON
        result = {
            "result": response,
            "session_id": session.session_id,
        }
        return json.dumps(result)

    return subagent_dispatch
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py tests/tools/test_subagent_tool.py
git commit -m "feat(tools): add subagent_dispatch tool factory"
```

---

## Task 4: Add tests for tool schema and self-exclusion

**Files:**
- Modify: `tests/tools/test_subagent_tool.py`

**Step 1: Write additional tests**

Add to `tests/tools/test_subagent_tool.py`:

```python
    def test_tool_has_correct_schema(self, tmp_path: Path):
        """Subagent dispatch tool should have correct name, description, and parameters."""
        config = self._create_test_config(tmp_path)

        # Create multiple agents
        for agent_id, name, desc in [
            ("reviewer", "Code Reviewer", "Reviews code for quality"),
            ("planner", "Task Planner", "Plans and organizes tasks"),
        ]:
            agent_dir = config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "caller", context)

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

    def test_tool_excludes_calling_agent(self, tmp_path: Path):
        """Subagent dispatch tool should exclude the calling agent from enum."""
        config = self._create_test_config(tmp_path)

        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-a", "Agent A", "First agent"),
            ("agent-b", "Agent B", "Second agent"),
            ("agent-c", "Agent C", "Third agent"),
        ]:
            agent_dir = config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        # When agent-b calls the factory, it should be excluded
        tool_func = create_subagent_dispatch_tool(loader, "agent-b", context)

        assert tool_func is not None
        enum_ids = set(tool_func.parameters["properties"]["agent_id"]["enum"])
        assert "agent-a" in enum_ids
        assert "agent-c" in enum_ids
        assert "agent-b" not in enum_ids  # Excluded!
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/tools/test_subagent_tool.py
git commit -m "test(tools): add schema and self-exclusion tests for subagent_dispatch"
```

---

## Task 5: Add async test for dispatch execution

**Files:**
- Modify: `tests/tools/test_subagent_tool.py`

**Step 1: Write async test**

Add to `tests/tools/test_subagent_tool.py`:

```python
from unittest.mock import AsyncMock, patch

    @pytest.mark.anyio
    async def test_tool_dispatches_to_subagent(self, tmp_path: Path):
        """Subagent dispatch tool should create session and return result + session_id."""
        config = self._create_test_config(tmp_path)

        # Create target agent
        agent_dir = config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text("""---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "caller", context)
        assert tool_func is not None

        # Mock the LLM response
        with patch.object(
            context.agent_loader.load("target-agent").__class__,
            "__init__",
            return_value=None,
        ):
            # We'll mock at the session.chat level instead
            pass

        # Simpler approach: mock Agent and Session
        mock_response = "Task completed successfully"

        with patch("picklebot.tools.subagent_tool.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-123"
            mock_session.chat = AsyncMock(return_value=mock_response)

            # Execute
            result = await tool_func.execute(
                agent_id="target-agent", task="Do something"
            )

            # Verify
            import json
            parsed = json.loads(result)
            assert parsed["result"] == "Task completed successfully"
            assert parsed["session_id"] == "test-session-123"

            # Verify session.chat was called with correct message
            mock_session.chat.assert_called_once_with("Do something", SilentFrontend())

    @pytest.mark.anyio
    async def test_tool_includes_context_in_message(self, tmp_path: Path):
        """Subagent dispatch tool should include context in user message."""
        config = self._create_test_config(tmp_path)

        # Create target agent
        agent_dir = config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text("""---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "caller", context)
        assert tool_func is not None

        with patch("picklebot.tools.subagent_tool.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-456"
            mock_session.chat = AsyncMock(return_value="Done")

            # Execute with context
            result = await tool_func.execute(
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
git commit -m "test(tools): add async execution tests for subagent_dispatch"
```

---

## Task 6: Register dispatch tool in Agent class

**Files:**
- Modify: `src/picklebot/core/agent.py`
- Test: `tests/core/test_agent.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
def test_agent_registers_subagent_dispatch_tool(tmp_path: Path) -> None:
    """Agent should always register subagent_dispatch tool when other agents exist."""
    config = _create_test_config(tmp_path)

    # Create another agent (so dispatch tool has something to dispatch to)
    other_agent_dir = config.agents_path / "other-agent"
    other_agent_dir.mkdir(parents=True)
    other_agent_file = other_agent_dir / "AGENT.md"
    other_agent_file.write_text("""---
name: Other Agent
description: Another agent for testing
---

You are another agent.
""")

    agent_def = _create_test_agent_def()
    agent_def.description = "Test agent"  # Add description
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that subagent_dispatch tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names


def test_agent_skips_subagent_dispatch_when_no_other_agents(tmp_path: Path) -> None:
    """Agent should NOT register subagent_dispatch tool when no other agents exist."""
    config = _create_test_config(tmp_path)
    # Don't create any other agents

    agent_def = _create_test_agent_def()
    agent_def.description = "Test agent"
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names
```

Also update `_create_test_agent_def` to include description:

```python
def _create_test_agent_def() -> AgentDef:
    """Create a minimal test agent definition."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent for unit testing",  # Add this
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_agent_registers_subagent_dispatch_tool -v`
Expected: FAIL with "subagent_dispatch" not in tool_names

**Step 3: Write minimal implementation**

Modify `src/picklebot/core/agent.py`:

Add import at top:
```python
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
```

Update `__init__` to register dispatch tool:
```python
def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
    self.agent_def = agent_def
    self.context = context
    # tools currently is initialized within Agent class.
    # This is intentional, in case agent will have its own tool regitry config later.
    self.tools = ToolRegistry.with_builtins()
    self.llm = LLMProvider.from_config(agent_def.llm)

    # Add skill tool if allowed
    if agent_def.allow_skills:
        self._register_skill_tool()

    # Add subagent dispatch tool
    self._register_subagent_tool()

def _register_subagent_tool(self) -> None:
    """Register the subagent dispatch tool if agents are available."""
    subagent_tool = create_subagent_dispatch_tool(
        self.context.agent_loader,
        self.agent_def.id,
        self.context
    )
    if subagent_tool:
        self.tools.register(subagent_tool)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "feat(agent): register subagent_dispatch tool in Agent.__init__"
```

---

## Task 7: Update existing agent definitions with description

**Files:**
- Check: `~/.pickle-bot/agents/*/AGENT.md` (user config directory)

**Step 1: Check for existing agents**

Run: `ls -la ~/.pickle-bot/agents/`

If any AGENT.md files exist, add `description` field to their frontmatter.

Example:
```markdown
---
name: Pickle
description: A helpful general-purpose assistant
---
```

**Step 2: Test with actual agent**

Run: `uv run picklebot chat -a <agent-name>`

Try dispatching to another agent if available.

**Step 3: Commit (if any changes)**

```bash
git add ~/.pickle-bot/agents/
git commit -m "docs(agents): add description field to agent definitions"
```

---

## Task 8: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run ruff check .`

Expected: No errors

**Step 3: Run type checking**

Run: `uv run mypy .`

Expected: No errors (or only pre-existing ones)

**Step 4: Final commit (if needed)**

```bash
git status
# Fix any issues, then:
git add .
git commit -m "fix: resolve any remaining issues"
```

---

## Summary

**Files created:**
- `src/picklebot/tools/subagent_tool.py`
- `tests/tools/test_subagent_tool.py`

**Files modified:**
- `src/picklebot/core/agent_loader.py` - Add `description` field and `discover_agents()` method
- `src/picklebot/core/agent.py` - Register dispatch tool in `__init__`
- `tests/core/test_agent_loader.py` - Tests for description field and discover_agents
- `tests/core/test_agent.py` - Tests for dispatch tool registration
