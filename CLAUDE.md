# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run picklebot chat
uv run picklebot --help

# Development
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
uv run mypy .           # Type check
```

## Architecture

```
src/picklebot/
├── cli/           # Typer CLI (main.py, chat.py)
├── core/          # Agent, AgentSession, AgentDef, AgentLoader, HistoryStore
├── provider/      # LLM provider abstraction (base.py, providers.py)
├── tools/         # Tool system (base.py, registry.py, builtin_tools.py)
├── frontend/      # UI abstraction (base.py, console.py)
└── utils/         # Config, logging
```

### Key Components

**Agent** (`core/agent.py`): Main orchestrator that handles chat loops, tool calls, and LLM interaction. Receives `AgentDef`, builds context from session history, executes tool calls via ToolRegistry.

**AgentDef** (`core/agent_def.py`): Loaded agent definition containing id, name, system_prompt, llm config, and behavior settings. Created by `AgentLoader` from AGENT.md files.

**AgentLoader** (`core/agent_loader.py`): Parses AGENT.md files with YAML frontmatter, merges agent-specific LLM settings with shared config. Raises `AgentNotFoundError` or `InvalidAgentError` on failures.

**AgentSession** (`core/session.py`): Runtime state for a conversation. Manages in-memory message list and persists to HistoryStore. Async context manager.

**HistoryStore** (`core/history.py`): JSON file-based persistence. Directory: `~/.pickle-bot/history/sessions/` with an `index.json` for fast session listing. `HistoryMessage` has `from_message()` and `to_message()` methods for litellm Message conversion.

**LLMProvider** (`provider/base.py`): Abstract base using litellm. Subclasses only need to set `provider_config_name` for auto-registration. Built-in: ZaiProvider, OpenAIProvider, AnthropicProvider.

**ToolRegistry** (`tools/registry.py`): Registers tools and generates schemas for LiteLLM function calling. Use `@tool` decorator or inherit from `BaseTool`.

**Frontend** (`frontend/base.py`): Abstract UI interface. `ConsoleFrontend` uses Rich for terminal output. Key method: `show_transient()` displays temporary status during tool calls.

### Configuration

Stored in `~/.pickle-bot/`:
- `config.system.yaml` - System defaults (default_agent, paths)
- `config.user.yaml` - User overrides (llm settings, deep-merged)
- `agents/` - Agent definition folders
  - `agents/[name]/AGENT.md` - Agent config with YAML frontmatter

Pydantic models in `utils/config.py`. Load via `Config.load(workspace_dir)`.

### Agent Definitions

Agents are defined in `~/.pickle-bot/agents/[name]/AGENT.md`:

```markdown
---
name: Agent Display Name
provider: openai        # Optional: override shared LLM
model: gpt-4            # Optional: override shared LLM
temperature: 0.7
max_tokens: 4096
---

You are a helpful assistant...
```

Load agents via `AgentLoader`:
```python
loader = AgentLoader(config.agents_path, config.llm)
agent_def = loader.load("agent-name")
```

### Skill System

Skills are user-defined capabilities that can be loaded on-demand by the LLM. Skills are defined in `~/.pickle-bot/skills/[name]/SKILL.md` files with YAML frontmatter.

**Skill Definition Format:**

```markdown
---
name: Skill Display Name
description: Brief description for LLM to decide whether to load
---

# Skill Name

Instructions for the skill...
```

**Enabling Skills:**

Add `allow_skills: true` to your agent's AGENT.md:

```markdown
---
name: My Agent
allow_skills: true
---

You are a helpful assistant...
```

**Available Skills:**

When skills are enabled, the LLM has access to a "skill" tool that presents all available skills and can load their content on demand.

## Patterns

### Adding a Tool

```python
from picklebot.tools.base import tool

@tool(
    name="my_tool",
    description="Does something",
    parameters={"type": "object", "properties": {...}, "required": [...]},
)
async def my_tool(arg: str) -> str:
    return f"Result: {arg}"
```

### Adding an LLM Provider

```python
from picklebot.provider.base import LLMProvider

class MyProvider(LLMProvider):
    provider_config_name = ["myprovider", "my_provider"]
    # Inherits default chat() via litellm
```

### Message Conversion

`HistoryMessage` has bidirectional conversion with litellm `Message` format:

```python
# Message → HistoryMessage (for persistence)
history_msg = HistoryMessage.from_message(message)

# HistoryMessage → Message (for LLM context)
message = history_msg.to_message()
```
