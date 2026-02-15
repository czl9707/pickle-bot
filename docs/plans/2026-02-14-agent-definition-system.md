# Agent Definition System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable multi-agent support by loading agent definitions from `~/.pickle-bot/agents/[name]/AGENT.md` files with YAML frontmatter.

**Architecture:** New `AgentDef` model holds loaded agent config. `AgentLoader` parses AGENT.md files and merges LLM settings with shared config. Config removes `AgentConfig` and adds `default_agent`/`agents_path`. Agent class receives `AgentDef` instead of `Config`.

**Tech Stack:** Python, Pydantic, YAML, markdown-it-py (or custom frontmatter parsing)

---

## Task 1: Create AgentDef Model

**Files:**
- Create: `src/picklebot/core/agent_def.py`
- Create: `tests/core/test_agent_def.py`

**Step 1: Write the failing test for AgentBehaviorConfig**

```python
# tests/core/test_agent_def.py
"""Tests for AgentDef model."""

import pytest
from picklebot.core.agent_def import AgentBehaviorConfig


class TestAgentBehaviorConfig:
    def test_defaults(self):
        """Default values for behavior config."""
        config = AgentBehaviorConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_custom_values(self):
        """Custom values for behavior config."""
        config = AgentBehaviorConfig(temperature=0.5, max_tokens=4096)
        assert config.temperature == 0.5
        assert config.max_tokens == 4096
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_def.py -v`
Expected: FAIL with "No module named 'picklebot.core.agent_def'"

**Step 3: Write AgentBehaviorConfig and AgentDef models**

```python
# src/picklebot/core/agent_def.py
"""Agent definition models."""

from pydantic import BaseModel, Field

from picklebot.utils.config import LLMConfig


class AgentBehaviorConfig(BaseModel):
    """Agent behavior settings."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)


class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    system_prompt: str
    llm: LLMConfig
    behavior: AgentBehaviorConfig
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_def.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_def.py tests/core/test_agent_def.py
git commit -m "feat(core): add AgentDef and AgentBehaviorConfig models"
```

---

## Task 2: Create AgentLoader - Exceptions

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test for exceptions**

```python
# tests/core/test_agent_loader.py
"""Tests for AgentLoader."""

import pytest
from picklebot.core.agent_loader import AgentNotFoundError, InvalidAgentError


class TestExceptions:
    def test_agent_not_found_error(self):
        """AgentNotFoundError includes agent_id."""
        error = AgentNotFoundError("pickle")
        assert "pickle" in str(error)
        assert error.agent_id == "pickle"

    def test_invalid_agent_error(self):
        """InvalidAgentError includes agent_id and reason."""
        error = InvalidAgentError("pickle", "missing name field")
        assert "pickle" in str(error)
        assert "missing name field" in str(error)
        assert error.agent_id == "pickle"
        assert error.reason == "missing name field"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: FAIL with "No module named 'picklebot.core.agent_loader'"

**Step 3: Write exception classes**

```python
# src/picklebot/core/agent_loader.py
"""Agent definition loader."""

from pathlib import Path

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_def import AgentDef, AgentBehaviorConfig


class AgentError(Exception):
    """Base error for agent loading."""
    pass


class AgentNotFoundError(AgentError):
    """Agent folder or AGENT.md doesn't exist."""

    def __init__(self, agent_id: str):
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class InvalidAgentError(AgentError):
    """Agent file is malformed."""

    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"Invalid agent '{agent_id}': {reason}")
        self.agent_id = agent_id
        self.reason = reason
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(core): add AgentLoader exceptions"
```

---

## Task 3: Create AgentLoader - Parsing

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test for frontmatter parsing**

```python
# Add to tests/core/test_agent_loader.py
from pathlib import Path
import tempfile

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_loader import AgentLoader


class TestAgentLoaderParsing:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_agents_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_simple_agent(self, temp_agents_dir, shared_llm):
        """Parse agent with name and prompt only."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)
        agent_def = loader.load("pickle")

        assert agent_def.id == "pickle"
        assert agent_def.name == "Pickle"
        assert agent_def.system_prompt == "You are a helpful assistant."
        assert agent_def.llm.provider == "test"

    def test_parse_agent_with_llm_overrides(self, temp_agents_dir, shared_llm):
        """Parse agent with LLM overrides."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "name: Pickle\n"
            "provider: openai\n"
            "model: gpt-4\n"
            "temperature: 0.5\n"
            "max_tokens: 8192\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)
        agent_def = loader.load("pickle")

        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.behavior.temperature == 0.5
        assert agent_def.behavior.max_tokens == 8192
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing -v`
Expected: FAIL with "AgentLoader has no attribute 'load'"

**Step 3: Implement AgentLoader class**

```python
# Replace entire src/picklebot/core/agent_loader.py
"""Agent definition loader."""

from pathlib import Path
from typing import Any

import yaml

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_def import AgentDef, AgentBehaviorConfig


class AgentError(Exception):
    """Base error for agent loading."""
    pass


class AgentNotFoundError(AgentError):
    """Agent folder or AGENT.md doesn't exist."""

    def __init__(self, agent_id: str):
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class InvalidAgentError(AgentError):
    """Agent file is malformed."""

    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"Invalid agent '{agent_id}': {reason}")
        self.agent_id = agent_id
        self.reason = reason


class AgentLoader:
    """Loads agent definitions from AGENT.md files."""

    def __init__(self, agents_dir: Path, shared_llm: LLMConfig):
        """
        Initialize AgentLoader.

        Args:
            agents_dir: Directory containing agent folders
            shared_llm: Shared LLM config to fall back to
        """
        self.agents_dir = agents_dir
        self.shared_llm = shared_llm

    def load(self, agent_id: str) -> AgentDef:
        """
        Load agent by ID.

        Args:
            agent_id: Agent folder name

        Returns:
            AgentDef with merged settings

        Raises:
            AgentNotFoundError: Agent folder or file doesn't exist
            InvalidAgentError: Agent file is malformed
        """
        agent_file = self.agents_dir / agent_id / "AGENT.md"
        if not agent_file.exists():
            raise AgentNotFoundError(agent_id)

        try:
            frontmatter, body = self._parse_agent_file(agent_file)
        except Exception as e:
            raise InvalidAgentError(agent_id, str(e))

        if "name" not in frontmatter:
            raise InvalidAgentError(agent_id, "missing required field: name")

        merged_llm = self._merge_llm_config(frontmatter)

        return AgentDef(
            id=agent_id,
            name=frontmatter["name"],
            system_prompt=body.strip(),
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
        )

    def _parse_agent_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter + markdown body.

        Args:
            path: Path to AGENT.md file

        Returns:
            Tuple of (frontmatter dict, body string)
        """
        content = path.read_text()

        if not content.startswith("---"):
            return {}, content

        # Find closing ---
        lines = content.split("\n")
        end_index = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = i
                break

        if end_index is None:
            return {}, content

        frontmatter_text = "\n".join(lines[1:end_index])
        body = "\n".join(lines[end_index + 1 :])

        frontmatter = yaml.safe_load(frontmatter_text) or {}
        return frontmatter, body

    def _merge_llm_config(self, frontmatter: dict[str, Any]) -> LLMConfig:
        """
        Merge agent overrides with shared LLM config.

        Args:
            frontmatter: Parsed frontmatter dict

        Returns:
            LLMConfig with merged settings
        """
        return LLMConfig(
            provider=frontmatter.get("provider", self.shared_llm.provider),
            model=frontmatter.get("model", self.shared_llm.model),
            api_key=frontmatter.get("api_key", self.shared_llm.api_key),
            api_base=frontmatter.get("api_base", self.shared_llm.api_base),
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(core): implement AgentLoader with frontmatter parsing"
```

---

## Task 4: Create AgentLoader - Error Tests

**Files:**
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Write the failing tests for error cases**

```python
# Add to tests/core/test_agent_loader.py

class TestAgentLoaderErrors:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_agents_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_raises_not_found_when_folder_missing(self, temp_agents_dir, shared_llm):
        """Raise AgentNotFoundError when folder doesn't exist."""
        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(AgentNotFoundError) as exc:
            loader.load("nonexistent")

        assert exc.value.agent_id == "nonexistent"

    def test_raises_not_found_when_file_missing(self, temp_agents_dir, shared_llm):
        """Raise AgentNotFoundError when AGENT.md doesn't exist."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        # No AGENT.md created

        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(AgentNotFoundError):
            loader.load("pickle")

    def test_raises_invalid_when_missing_name(self, temp_agents_dir, shared_llm):
        """Raise InvalidAgentError when name field is missing."""
        agent_dir = temp_agents_dir / "pickle"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\n"
            "temperature: 0.5\n"
            "---\n"
            "You are a helpful assistant."
        )

        loader = AgentLoader(temp_agents_dir, shared_llm)

        with pytest.raises(InvalidAgentError) as exc:
            loader.load("pickle")

        assert "name" in exc.value.reason
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderErrors -v`
Expected: PASS (implementation already handles these cases)

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "test(core): add error case tests for AgentLoader"
```

---

## Task 5: Update Config Model

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `tests/utils/test_config.py`

**Step 1: Write the failing tests**

```python
# Add to tests/utils/test_config.py

class TestAgentsPath:
    def test_resolves_relative_agents_path(self, minimal_llm_config):
        """Relative agents_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
            agents_path=Path("agents"),
        )
        assert config.agents_path == Path("/workspace/agents")

    def test_default_agents_path(self, minimal_llm_config):
        """Default agents_path should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
        )
        assert config.agents_path == Path("/workspace/agents")

    def test_rejects_absolute_agents_path(self, minimal_llm_config):
        """Absolute agents_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                default_agent="pickle",
                agents_path=Path("/etc/agents"),
            )
        assert "agents_path must be relative" in str(exc.value)

    def test_default_agent_required(self, minimal_llm_config):
        """default_agent is required."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
            )
        assert "default_agent" in str(exc.value)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestAgentsPath -v`
Expected: FAIL (missing fields)

**Step 3: Update Config model**

```python
# Replace src/picklebot/utils/config.py
"""Configuration management for pickle-bot."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Configuration Models
# ============================================================================


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str
    model: str
    api_key: str
    api_base: str | None = None

    @field_validator("api_base")
    @classmethod
    def api_base_must_be_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("api_base must be a valid URL")
        return v


# ============================================================================
# Main Configuration Class
# ============================================================================


class Config(BaseModel):
    """
    Main configuration for pickle-bot.

    Configuration is loaded from ~/.pickle-bot/:
    1. config.system.yaml - System defaults (shipped with the app)
    2. config.user.yaml - User overrides (optional, overrides system)

    User config takes precedence over system config.
    """

    workspace: Path
    llm: LLMConfig
    default_agent: str
    agents_path: Path = Field(default=Path("agents"))
    logging_path: Path = Field(default=Path(".logs"))
    history_path: Path = Field(default=Path(".history"))

    @model_validator(mode="after")
    def resolve_paths(self) -> "Config":
        """Resolve relative paths to absolute using workspace."""
        for field_name in ("agents_path", "logging_path", "history_path"):
            path = getattr(self, field_name)
            if path.is_absolute():
                raise ValueError(f"{field_name} must be relative, got: {path}")
            setattr(self, field_name, self.workspace / path)
        return self

    @classmethod
    def load(cls, workspace_dir: Path) -> "Config":
        """
        Load configuration from ~/.pickle-bot/.

        Args:
            workspace_dir: Path to workspace_dir directory. Defaults to ~/.pickle-bot/

        Returns:
            Config instance with all settings loaded and validated

        Raises:
            FileNotFoundError: If config directory doesn't exist
            ValidationError: If configuration is invalid
        """

        config_data: dict = {"workspace": workspace_dir}

        system_config = workspace_dir / "config.system.yaml"
        user_config = workspace_dir / "config.user.yaml"

        if system_config.exists():
            with open(system_config) as f:
                system_data = yaml.safe_load(f) or {}
            config_data.update(system_data)

        if user_config.exists():
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
            # Deep merge user config over system config
            config_data = cls._deep_merge(config_data, user_data)

        # Validate and create Config instance
        return cls.model_validate(config_data)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge override dict into base dict.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "refactor(config): remove AgentConfig, add default_agent and agents_path"
```

---

## Task 6: Update Agent Class

**Files:**
- Modify: `src/picklebot/core/agent.py`
- Modify: `tests/core/test_agent.py`

**Step 1: Read existing agent tests**

Run: `cat tests/core/test_agent.py` to understand what tests exist

**Step 2: Update Agent class to use AgentDef**

```python
# Modify src/picklebot/core/agent.py
# Replace imports and dataclass fields

import uuid
import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from typing import TYPE_CHECKING

from picklebot.core.context import SharedContext
from picklebot.core.agent_def import AgentDef
from picklebot.provider import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.core.history import HistoryMessage

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam,
)


if TYPE_CHECKING:
    from picklebot.frontend import Frontend
    from picklebot.provider import LLMToolCall


@dataclass
class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM, tools, and config
    that sessions use for chatting.
    """

    agent_def: AgentDef  # Changed from agent_config
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> "AgentSession":
        """
        Create a new conversation session.

        Returns:
            A new Session instance with self as the agent reference.
        """
        session_id = str(uuid.uuid4())
        session = AgentSession(
            session_id=session_id,
            agent_id=self.agent_def.id,  # Changed
            context=self.context,
            agent=self,
        )

        self.context.history_store.create_session(self.agent_def.id, session_id)  # Changed
        return session

    # ... rest of the file stays the same until _build_messages ...

    def _build_messages(self) -> list[Message]:
        """
        Build messages for LLM API call.

        Returns:
            List of messages compatible with litellm
        """
        messages: list[Message] = [
            {"role": "system", "content": self.agent_def.system_prompt}  # Changed
        ]
        messages.extend(self.get_history(50))

        return messages
```

**Step 3: Run all tests to find breakages**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: Some tests may fail due to AgentConfig removal

**Step 4: Fix failing tests**

Update tests to use AgentDef instead of AgentConfig where needed.

**Step 5: Run all tests to verify**

Run: `uv run pytest -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "refactor(agent): accept AgentDef instead of AgentConfig"
```

---

## Task 7: Update ConsoleFrontend

**Files:**
- Modify: `src/picklebot/frontend/console.py`

**Step 1: Update ConsoleFrontend to use AgentDef**

```python
# Modify src/picklebot/frontend/console.py
"""Console frontend implementation using Rich."""

import contextlib
from typing import Iterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent_def import AgentDef
from .base import Frontend


class ConsoleFrontend(Frontend):
    """Console-based frontend using Rich for formatting."""

    def __init__(self, agent_def: AgentDef):
        """
        Initialize console frontend.

        Args:
            agent_def: Agent definition
        """
        self.agent_def = agent_def
        self.console = Console()

    def show_welcome(self) -> None:
        """Display welcome message panel."""
        self.console.print(
            Panel(
                Text(f"Welcome to {self.agent_def.name}!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    def get_user_input(self) -> str:
        """Get user input."""
        return self.console.input("[bold green]You:[/bold green] ")

    def show_agent_response(self, content: str) -> None:
        """Display agent's final response to user."""
        self.console.print(
            f"[bold cyan]{self.agent_def.name}:[/bold cyan] {content}\n"
        )

    def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        self.console.print(content)

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield
```

**Step 2: Commit**

```bash
git add src/picklebot/frontend/console.py
git commit -m "refactor(frontend): accept AgentDef instead of AgentConfig"
```

---

## Task 8: Update ChatLoop and Add --agent Flag

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Update ChatLoop to use AgentLoader**

```python
# Replace src/picklebot/cli/chat.py
"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, SharedContext
from picklebot.core.agent_loader import AgentLoader
from picklebot.provider import LLMProvider
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend
from picklebot.tools.registry import ToolRegistry


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        # Load agent definition
        loader = AgentLoader(config.agents_path, config.llm)
        self.agent_def = loader.load(self.agent_id)

        self.frontend = ConsoleFrontend(self.agent_def)
        self.context = SharedContext(config=config)

        self.agent = Agent(
            agent_def=self.agent_def,
            llm=LLMProvider.from_config(self.agent_def.llm),
            tools=ToolRegistry.with_builtins(),
            context=self.context,
        )

    async def run(self) -> None:
        """Run the interactive chat loop."""
        session = self.agent.new_session()
        self.frontend.show_welcome()

        while True:
            try:
                user_input = self.frontend.get_user_input()

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                response = await session.chat(user_input, self.frontend)
                self.frontend.show_agent_response(response)

            except KeyboardInterrupt:
                self.frontend.show_system_message(
                    "\n[yellow]Session interrupted.[/yellow]"
                )
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
```

**Step 2: Update main.py to add --agent flag**

Read `src/picklebot/cli/main.py` first to understand current structure, then add the flag.

**Step 3: Commit**

```bash
git add src/picklebot/cli/chat.py src/picklebot/cli/main.py
git commit -m "feat(cli): add AgentLoader integration and --agent flag"
```

---

## Task 9: Update Core Exports

**Files:**
- Modify: `src/picklebot/core/__init__.py`

**Step 1: Add new exports**

```python
# Update src/picklebot/core/__init__.py
from picklebot.core.agent import Agent, AgentSession
from picklebot.core.agent_def import AgentDef, AgentBehaviorConfig
from picklebot.core.agent_loader import AgentLoader, AgentNotFoundError, InvalidAgentError
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore, HistoryMessage, HistorySession

__all__ = [
    "Agent",
    "AgentSession",
    "AgentDef",
    "AgentBehaviorConfig",
    "AgentLoader",
    "AgentNotFoundError",
    "InvalidAgentError",
    "SharedContext",
    "HistoryStore",
    "HistoryMessage",
    "HistorySession",
]
```

**Step 2: Commit**

```bash
git add src/picklebot/core/__init__.py
git commit -m "feat(core): export AgentDef and AgentLoader"
```

---

## Task 10: Migrate User Config

**Files:**
- Create: `~/.pickle-bot/agents/pickle/AGENT.md`
- Modify: `~/.pickle-bot/config.system.yaml`

**Step 1: Create pickle agent directory and file**

```bash
mkdir -p ~/.pickle-bot/agents/pickle
```

**Step 2: Create AGENT.md**

```markdown
---
name: Pickle
temperature: 0.7
max_tokens: 4096
---

You are pickle-bot, a helpful AI assistant with access to various skills.
```

**Step 3: Update config.system.yaml**

```yaml
default_agent: pickle
logging_path: .logs
history_path: .history
```

**Step 4: Test the changes manually**

Run: `uv run picklebot chat`
Expected: Chat starts with pickle agent

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: migrate to agent definition system"
```

---

## Verification

After all tasks:

1. `uv run pytest -v` — All tests pass
2. `uv run mypy .` — Type checking passes
3. `uv run ruff check .` — Linting passes
4. `uv run picklebot chat` — CLI works with default agent
5. `uv run picklebot chat --agent pickle` — CLI works with explicit agent
