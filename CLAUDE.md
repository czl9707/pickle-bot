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
├── core/          # Agent, AgentSession, HistoryStore
├── provider/      # LLM provider abstraction (base.py, providers.py)
├── tools/         # Tool system (base.py, registry.py, builtin_tools.py)
├── frontend/      # UI abstraction (base.py, console.py)
└── utils/         # Config, logging
```

### Key Components

**Agent** (`core/agent.py`): Main orchestrator that handles chat loops, tool calls, and LLM interaction. Receives messages, builds context from session history, executes tool calls via ToolRegistry.

**AgentSession** (`core/session.py`): Runtime state for a conversation. Manages in-memory message list and persists to HistoryStore. Async context manager.

**HistoryStore** (`core/history.py`): JSON file-based persistence. Directory: `~/.pickle-bot/history/sessions/` with an `index.json` for fast session listing.

**LLMProvider** (`provider/base.py`): Abstract base using litellm. Subclasses only need to set `provider_config_name` for auto-registration. Built-in: ZaiProvider, OpenAIProvider, AnthropicProvider.

**ToolRegistry** (`tools/registry.py`): Registers tools and generates schemas for LiteLLM function calling. Use `@tool` decorator or inherit from `BaseTool`.

**Frontend** (`frontend/base.py`): Abstract UI interface. `ConsoleFrontend` uses Rich for terminal output. Key method: `show_transient()` displays temporary status during tool calls.

### Configuration

Stored in `~/.pickle-bot/`:
- `config.system.yaml` - System defaults
- `config.user.yaml` - User overrides (deep-merged)

Pydantic models in `utils/config.py`. Load via `Config.load(workspace_dir)`.

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
