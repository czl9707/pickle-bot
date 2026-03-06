# Multi-Layer Prompt System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement layered system prompt assembly with 5 layers: Identity, Soul, Bootstrap, Runtime, Channel.

**Architecture:** Create a PromptBuilder class that assembles prompts from multiple sources at runtime. AgentLoader loads per-agent SOUL.md files. CronLoader requires description field.

**Tech Stack:** Python, Pydantic, pathlib

---

## Task 1: Add description field to CronDef

**Files:**
- Modify: `src/picklebot/core/cron_loader.py:25-33`
- Modify: `tests/helpers.py:85-119`
- Test: `tests/core/test_cron_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_cron_loader.py`:

```python
def test_cron_def_requires_description(tmp_path):
    """CronDef should require description field."""
    from picklebot.core.cron_loader import CronDef
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        CronDef(
            id="test",
            name="Test Cron",
            agent="pickle",
            schedule="0 * * * *",
            prompt="Test prompt",
        )

    assert "description" in str(exc_info.value)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_cron_loader.py::test_cron_def_requires_description -v`
Expected: FAIL - description field missing

**Step 3: Add description field to CronDef**

Modify `src/picklebot/core/cron_loader.py`:

```python
class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    description: str  # Mandatory description
    agent: str
    schedule: str
    prompt: str
    one_off: bool = False
```

**Step 4: Update _parse_cron_def to include description**

In `src/picklebot/core/cron_loader.py`, update the CronDef construction:

```python
def _parse_cron_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> CronDef | None:
    """Parse cron definition from frontmatter (callback for discover_definitions)."""
    body = substitute_template(body, get_template_variables(self.config))

    try:
        return CronDef(
            id=def_id,
            name=frontmatter["name"],
            description=frontmatter["description"],  # Add this line
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
            prompt=body.strip(),
            one_off=frontmatter.get("one_off", False),
        )
    except ValidationError as e:
        logger.warning(f"Invalid cron '{def_id}': {e}")
        return None
```

**Step 5: Update tests/helpers.py create_test_cron**

```python
def create_test_cron(
    workspace: Path,
    cron_id: str = "test-cron",
    name: str = "Test Cron",
    description: str = "A test cron job",  # Add this
    agent: str = "pickle",
    schedule: str = "0 * * * *",
    prompt: str = "Check for updates.",
    one_off: bool = False,
) -> Path:
    """Create a minimal test cron in workspace."""
    crons_dir = workspace / "crons"
    crons_dir.mkdir(parents=True, exist_ok=True)

    cron_dir = crons_dir / cron_id
    cron_dir.mkdir(parents=True, exist_ok=True)

    cron_md = cron_dir / "CRON.md"
    cron_md.write_text(
        f'---\nname: {name}\ndescription: {description}\nagent: {agent}\nschedule: "{schedule}"\none_off: {one_off}\n---\n{prompt}\n'
    )

    return cron_dir
```

**Step 6: Run all cron tests to verify**

Run: `uv run pytest tests/core/test_cron_loader.py -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/helpers.py
git commit -m "feat(cron): add mandatory description field to CronDef"
```

---

## Task 2: Rename system_prompt to agent_md and add soul_md

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:18-27`
- Modify: `tests/conftest.py:35-43`
- Modify: `tests/core/test_agent.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent_loader.py`:

```python
def test_agent_def_has_agent_md_and_soul_md():
    """AgentDef should have agent_md and soul_md fields."""
    from picklebot.core.agent_loader import AgentDef
    from picklebot.utils.config import LLMConfig

    agent_def = AgentDef(
        id="test",
        name="Test",
        agent_md="You are a test agent.",
        soul_md="Be friendly.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
    )

    assert agent_def.agent_md == "You are a test agent."
    assert agent_def.soul_md == "Be friendly."
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_agent_def_has_agent_md_and_soul_md -v`
Expected: FAIL - fields don't exist

**Step 3: Update AgentDef model**

Modify `src/picklebot/core/agent_loader.py`:

```python
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    description: str = ""
    agent_md: str           # Renamed from system_prompt
    soul_md: str = ""       # New: personality traits
    llm: LLMConfig
    allow_skills: bool = False
    max_concurrency: int = Field(default=1, ge=1)
```

**Step 4: Update _parse_agent_def**

In `src/picklebot/core/agent_loader.py`, update the AgentDef construction:

```python
def _parse_agent_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> AgentDef:
    """Parse agent definition from frontmatter (callback for parse_definition)."""
    body = substitute_template(body, get_template_variables(self.config))
    llm_overrides = frontmatter.get("llm")
    merged_llm = self._merge_llm_config(llm_overrides)

    # Load SOUL.md if exists
    soul_md = self._load_soul_md(def_id)

    try:
        return AgentDef(
            id=def_id,
            name=frontmatter["name"],
            description=frontmatter.get("description", ""),
            agent_md=body.strip(),
            soul_md=soul_md,
            llm=merged_llm,
            allow_skills=frontmatter.get("allow_skills", False),
            max_concurrency=frontmatter.get("max_concurrency", 1),
        )
    except ValidationError as e:
        raise InvalidDefError("agent", def_id, str(e))
```

**Step 5: Add _load_soul_md method to AgentLoader**

In `src/picklebot/core/agent_loader.py`, add:

```python
def _load_soul_md(self, agent_id: str) -> str:
    """Load SOUL.md file for an agent if it exists.

    Args:
        agent_id: Agent identifier

    Returns:
        Content of SOUL.md or empty string if not found
    """
    soul_path = self.config.agents_path / agent_id / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text().strip()
    return ""
```

**Step 6: Update tests/conftest.py**

```python
@pytest.fixture
def test_agent_def(llm_config: LLMConfig) -> AgentDef:
    """Minimal AgentDef for testing."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        agent_md="You are a test assistant.",  # Changed from system_prompt
        llm=llm_config,
    )
```

**Step 7: Update tests/helpers.py create_test_agent**

```python
def create_test_agent(
    workspace: Path,
    agent_id: str = "test-agent",
    name: str = "Test Agent",
    description: str = "A test agent",
    agent_md: str = "You are a test assistant.",  # Renamed from system_prompt
    **kwargs,
) -> Path:
    """Create a minimal test agent in workspace."""
    agents_dir = workspace / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    agent_dir = agents_dir / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    frontmatter_lines = [
        f"name: {name}",
        f"description: {description}",
    ]
    for key, value in kwargs.items():
        if isinstance(value, str):
            frontmatter_lines.append(f"{key}: {value}")
        else:
            frontmatter_lines.append(f"{key}: {value}")

    frontmatter = "\n".join(frontmatter_lines)

    agent_md_file = agent_dir / "AGENT.md"
    agent_md_file.write_text(f"---\n{frontmatter}\n---\n{agent_md}\n")

    return agent_dir
```

**Step 8: Update tests/core/test_agent.py**

Replace all occurrences of `system_prompt` with `agent_md`:

```python
# Line 117
agent_def = AgentDef(
    id="test-agent",
    name="Test Agent",
    agent_md="You are a test assistant.",  # Changed
    llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
    allow_skills=allow_skills,
)

# Line 190-195
agent_def = AgentDef(
    id="test-agent",
    name="Test Agent",
    agent_md="You are a test assistant.",  # Changed
    llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
)

# Line 255
agent_def.system_prompt = "You are a test agent."  # This line becomes:
agent_def.agent_md = "You are a test agent."
```

**Step 9: Run tests to verify**

Run: `uv run pytest tests/core/test_agent_loader.py tests/core/test_agent.py -v`
Expected: All tests pass

**Step 10: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/conftest.py tests/helpers.py tests/core/test_agent.py
git commit -m "feat(agent): rename system_prompt to agent_md, add soul_md field"
```

---

## Task 3: Create PromptBuilder class

**Files:**
- Create: `src/picklebot/core/prompt_builder.py`
- Create: `tests/core/test_prompt_builder.py`

**Step 1: Write the failing test**

Create `tests/core/test_prompt_builder.py`:

```python
"""Tests for PromptBuilder."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from picklebot.core.prompt_builder import PromptBuilder
from picklebot.core.agent_loader import AgentDef
from picklebot.core.events import TelegramEventSource, CronEventSource
from picklebot.utils.config import LLMConfig


@pytest.fixture
def prompt_builder(tmp_path):
    """Create a PromptBuilder with temp workspace."""
    mock_cron_loader = MagicMock()
    mock_cron_loader.discover_crons.return_value = []
    return PromptBuilder(workspace_path=tmp_path, cron_loader=mock_cron_loader)


@pytest.fixture
def agent_def():
    """Create a test AgentDef."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        agent_md="You are a test agent.",
        soul_md="Be friendly and helpful.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
    )


class TestPromptBuilderBasic:
    """Tests for basic prompt building."""

    def test_build_includes_agent_md(self, prompt_builder, agent_def):
        """Prompt should include agent_md."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are a test agent." in prompt

    def test_build_includes_soul_md(self, prompt_builder, agent_def):
        """Prompt should include soul_md if present."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Be friendly and helpful." in prompt

    def test_build_without_soul_md(self, prompt_builder):
        """Prompt should work without soul_md."""
        agent_def_no_soul = AgentDef(
            id="test-agent",
            name="Test Agent",
            agent_md="You are a test agent.",
            soul_md="",  # Empty
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
        )
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def_no_soul
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are a test agent." in prompt
        assert "Personality" not in prompt


class TestPromptBuilderRuntime:
    """Tests for runtime context layer."""

    def test_build_includes_agent_id(self, prompt_builder, agent_def):
        """Prompt should include agent ID."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "test-agent" in prompt

    def test_build_includes_timestamp(self, prompt_builder, agent_def):
        """Prompt should include timestamp."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Time:" in prompt


class TestPromptBuilderChannel:
    """Tests for channel hints layer."""

    def test_build_telegram_hint(self, prompt_builder, agent_def):
        """Prompt should include Telegram hint."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are responding via telegram." in prompt

    def test_build_cron_hint(self, prompt_builder, agent_def):
        """Prompt should include cron hint."""
        source = CronEventSource(cron_id="daily-job")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are responding via cron" in prompt


class TestPromptBuilderBootstrap:
    """Tests for bootstrap context layer."""

    def test_build_includes_bootstrap_md(self, prompt_builder, agent_def, tmp_path):
        """Prompt should include BOOTSTRAP.md content."""
        bootstrap_md = tmp_path / "BOOTSTRAP.md"
        bootstrap_md.write_text("Workspace guidelines here.")

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Workspace guidelines here." in prompt

    def test_build_includes_agents_md(self, prompt_builder, agent_def, tmp_path):
        """Prompt should include AGENTS.md content."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Available agents: cookie, pickle.")

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Available agents: cookie, pickle." in prompt

    def test_build_includes_cron_list(self, agent_def, tmp_path):
        """Prompt should include cron list."""
        from picklebot.core.cron_loader import CronDef

        mock_cron = CronDef(
            id="daily",
            name="Daily Summary",
            description="Sends daily summary",
            agent="pickle",
            schedule="0 9 * * *",
            prompt="Summarize today.",
        )
        mock_cron_loader = MagicMock()
        mock_cron_loader.discover_crons.return_value = [mock_cron]

        builder = PromptBuilder(workspace_path=tmp_path, cron_loader=mock_cron_loader)

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = builder.build(session)

        assert "Daily Summary" in prompt
        assert "Sends daily summary" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_prompt_builder.py -v`
Expected: FAIL - module not found

**Step 3: Create PromptBuilder class**

Create `src/picklebot/core/prompt_builder.py`:

```python
"""Prompt builder that assembles system prompt from layers."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.agent_loader import AgentDef
    from picklebot.core.cron_loader import CronLoader
    from picklebot.core.events import EventSource


class PromptBuilder:
    """Assembles system prompt from layered sources.

    Layers (in order):
    1. Identity - AGENT.md body (agent_md)
    2. Soul - SOUL.md (personality, optional)
    3. Bootstrap - BOOTSTRAP.md + AGENTS.md + cron list
    4. Runtime - Agent ID + timestamp
    5. Channel - Platform name hint
    """

    def __init__(self, workspace_path: Path, cron_loader: "CronLoader"):
        self.workspace_path = workspace_path
        self.cron_loader = cron_loader

    def build(self, session) -> str:
        """Build the full system prompt from layers.

        Args:
            session: AgentSession with agent_def and source

        Returns:
            Assembled system prompt string
        """
        layers = []

        # Layer 1: Identity
        layers.append(session.agent.agent_def.agent_md)

        # Layer 2: Soul (optional)
        if session.agent.agent_def.soul_md:
            layers.append(f"## Personality\n\n{session.agent.agent_def.soul_md}")

        # Layer 3: Bootstrap context
        bootstrap = self._load_bootstrap_context()
        if bootstrap:
            layers.append(bootstrap)

        # Layer 4: Runtime context
        layers.append(self._build_runtime_context(
            session.agent.agent_def.id,
            datetime.now(),
        ))

        # Layer 5: Channel hint
        layers.append(self._build_channel_hint(session.source))

        return "\n\n".join(layers)

    def _load_bootstrap_context(self) -> str:
        """Load BOOTSTRAP.md + AGENTS.md + cron list."""
        parts = []

        # BOOTSTRAP.md
        bootstrap_path = self.workspace_path / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            parts.append(bootstrap_path.read_text().strip())

        # AGENTS.md
        agents_path = self.workspace_path / "AGENTS.md"
        if agents_path.exists():
            parts.append(agents_path.read_text().strip())

        # Dynamic cron list
        cron_list = self._format_cron_list()
        if cron_list:
            parts.append(cron_list)

        return "\n\n".join(parts)

    def _format_cron_list(self) -> str:
        """Format crons as markdown list."""
        crons = self.cron_loader.discover_crons()
        if not crons:
            return ""

        lines = ["## Scheduled Tasks\n"]
        for cron in crons:
            lines.append(f"- **{cron.name}**: {cron.description}")
        return "\n".join(lines)

    def _build_runtime_context(self, agent_id: str, timestamp: datetime) -> str:
        """Build runtime info section."""
        return f"## Runtime\n\nAgent: {agent_id}\nTime: {timestamp.isoformat()}"

    def _build_channel_hint(self, source: "EventSource") -> str:
        """Build platform hint."""
        platform = source.platform_name or "unknown"
        return f"You are responding via {platform}."
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_prompt_builder.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/prompt_builder.py tests/core/test_prompt_builder.py
git commit -m "feat(core): add PromptBuilder for layered prompt assembly"
```

---

## Task 4: Integrate PromptBuilder into SharedContext

**Files:**
- Modify: `src/picklebot/core/context.py`
- Modify: `src/picklebot/core/agent.py:255-267`

**Step 1: Write the failing test**

Add to `tests/core/test_prompt_builder.py`:

```python
class TestPromptBuilderIntegration:
    """Tests for SharedContext integration."""

    def test_shared_context_has_prompt_builder(self, test_config):
        """SharedContext should have prompt_builder."""
        from picklebot.core.context import SharedContext

        context = SharedContext(config=test_config)
        assert hasattr(context, "prompt_builder")
        assert context.prompt_builder is not None

    def test_prompt_builder_uses_context_paths(self, test_config, tmp_path):
        """PromptBuilder should use workspace path from context."""
        from picklebot.core.context import SharedContext

        context = SharedContext(config=test_config)
        assert context.prompt_builder.workspace_path == tmp_path
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_prompt_builder.py::TestPromptBuilderIntegration -v`
Expected: FAIL - prompt_builder not found

**Step 3: Update SharedContext**

Modify `src/picklebot/core/context.py`:

```python
from typing import Any

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.commands.registry import CommandRegistry
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.prompt_builder import PromptBuilder  # Add import
from picklebot.core.routing import RoutingTable
from picklebot.core.skill_loader import SkillLoader
from picklebot.core.eventbus import EventBus
from picklebot.channels.base import Channel
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    command_registry: CommandRegistry
    channels_buses: list[Channel[Any]]
    eventbus: EventBus
    routing_table: RoutingTable
    prompt_builder: PromptBuilder  # Add field

    def __init__(
        self, config: Config, buses: list[Channel[Any]] | None = None
    ) -> None:
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)
        self.command_registry = CommandRegistry.with_builtins()

        if buses is not None:
            self.channels_buses = buses
        else:
            self.channels_buses = Channel.from_config(config)

        self.eventbus = EventBus(self)
        self.routing_table = RoutingTable(self)
        self.prompt_builder = PromptBuilder(config.workspace, self.cron_loader)  # Add
```

**Step 4: Run tests to verify**

Run: `uv run pytest tests/core/test_prompt_builder.py::TestPromptBuilderIntegration -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/context.py tests/core/test_prompt_builder.py
git commit -m "feat(context): integrate PromptBuilder into SharedContext"
```

---

## Task 5: Update AgentSession to use PromptBuilder

**Files:**
- Modify: `src/picklebot/core/agent.py:255-267`
- Test: `tests/core/test_agent.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
def test_session_builds_prompt_with_layers(test_agent):
    """AgentSession._build_messages should use PromptBuilder."""
    from picklebot.core.events import TelegramEventSource

    source = TelegramEventSource(user_id="123", chat_id="456")
    session = test_agent.new_session(source=source)

    messages = session._build_messages()
    system_prompt = messages[0]["content"]

    # Should include agent_md
    assert "You are a test assistant." in system_prompt
    # Should include channel hint
    assert "telegram" in system_prompt.lower()
    # Should include runtime
    assert "Agent:" in system_prompt
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_session_builds_prompt_with_layers -v`
Expected: FAIL - prompt doesn't include new layers

**Step 3: Update AgentSession._build_messages**

Modify `src/picklebot/core/agent.py`:

```python
def _build_messages(self) -> list[Message]:
    """
    Build messages for LLM API call.

    Returns:
        List of messages compatible with litellm
    """
    system_prompt = self.shared_context.prompt_builder.build(self)
    messages: list[Message] = [{"role": "system", "content": system_prompt}]
    messages.extend(self.get_history())

    return messages
```

**Step 4: Run tests to verify**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "feat(agent): use PromptBuilder for system prompt assembly"
```

---

## Task 6: Update remaining tests

**Files:**
- Modify: Various test files using `system_prompt`

**Step 1: Find and update all system_prompt references**

Run: `uv run grep -r "system_prompt" tests/`

**Step 2: Update each file**

In `tests/server/test_agent_worker.py`, `tests/api/test_agents.py`, etc., replace:
- `system_prompt` → `agent_md`

**Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: update all tests to use agent_md instead of system_prompt"
```

---

## Task 7: Update cron-ops skill

**Files:**
- Modify: `default_workspace/skills/cron-ops/SKILL.md`

**Step 1: Update skill to require description**

Modify `default_workspace/skills/cron-ops/SKILL.md`:

```markdown
---
name: cron-ops
description: Create, list, and delete scheduled cron jobs
---

Help users manage scheduled cron jobs in pickle-bot.

## What is a Cron?

A cron is a scheduled task that runs at specified intervals. Crons are stored as `CRON.md` files at `{{crons_path}}/<name>/CRON.md`.

## Schedule Syntax

Standard cron format: `minute hour day month weekday`

Examples:
- `0 9 * * *` - Every day at 9:00 AM
- `*/30 * * * *` - Every 30 minutes
- `0 0 * * 0` - Every Sunday at midnight

## Operations

### Create

1. Ask what task should run and when
2. Determine the schedule
3. Ask which agent should run the task
4. Ask for a brief description of what the cron does
5. Create the directory and CRON.md file

### List

Use `bash` to list directories:
```bash
ls {{crons_path}}
```

### Delete

1. List available crons
2. Confirm which one to delete
3. Use `bash` to remove:
```bash
rm -rf {{crons_path}}/<cron-name>
```

## Cron Prompt Guidelines

Cron jobs run in the background with no direct output to the user. The agent executing the cron has no conversation context.

**When the user asks to be notified** (e.g., "tell me", "let me know", "remind me"):
- Include `post_message` instruction in the prompt

**When the user doesn't ask for notification:**
- No `post_message` needed (e.g., background cleanup, data processing)

## Cron Template

```markdown
---
name: Cron Name
description: Brief description of what this cron does
agent: pickle
schedule: "0 9 * * *"
---

Task description for the agent to execute.
```

**With notification:**
```markdown
---
name: Daily Summary
description: Sends a daily summary of activity
agent: pickle
schedule: "0 9 * * *"
---

Check my inbox and use post_message to send me a summary.
```
```

**Step 2: Commit**

```bash
git add default_workspace/skills/cron-ops/SKILL.md
git commit -m "docs(skill): update cron-ops to require description field"
```

---

## Task 8: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`

**Step 2: Run linting**

Run: `uv run black . && uv run ruff check .`

**Step 3: Fix any issues**

**Step 4: Final commit (if needed)**

```bash
git add .
git commit -m "chore: fix linting issues"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add description field to CronDef |
| 2 | Rename system_prompt to agent_md, add soul_md |
| 3 | Create PromptBuilder class |
| 4 | Integrate PromptBuilder into SharedContext |
| 5 | Update AgentSession to use PromptBuilder |
| 6 | Update remaining tests |
| 7 | Update cron-ops skill |
| 8 | Run full test suite |
