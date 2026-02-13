# Pickle-Bot

A personal AI assistant with pluggable tools, built with Python.

## Features

- **Pluggable Tools System** - Function calling with custom tools
- **LLM Provider Abstraction** - Support for multiple LLM providers (Z.ai, OpenAI, Anthropic)
- **CLI Interface** - Clean command-line interface with Rich formatting
- **YAML Configuration** - Config-driven with system/user config split
- **Session History** - JSON-based conversation persistence

## Installation

```bash
git clone <repo-url>
cd pickle-bot
uv sync
```

## Configuration

Configuration is stored in `~/.pickle-bot/`:

```
~/.pickle-bot/
├── config.system.yaml    # System defaults
├── config.user.yaml      # Your overrides (optional)
└── history/              # Session persistence
    ├── sessions/
    └── index.json
```

**`~/.pickle-bot/config.system.yaml`:**
```yaml
agent:
  name: "pickle"
  system_prompt: "You are pickle-bot, a helpful AI assistant."
  behavior:
    temperature: 0.7
    max_tokens: 2048

history:
  path: ".history"

logging:
  path: ".logs"
```

**`~/.pickle-bot/config.user.yaml`:**
```yaml
llm:
  provider: zai
  model: "zai/glm-4.7"
  api_key: "your-api-key"
  api_base: "https://api.z.ai/api/coding/paas/v4"
```

## Usage

```bash
picklebot chat              # Start interactive chat
picklebot --help            # Show help
picklebot -c /path chat     # Use custom config directory
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read` | Read file contents |
| `write` | Write content to a file |
| `edit` | Replace text in a file |
| `bash` | Execute shell commands |

## Project Structure

```
src/picklebot/
├── cli/           # CLI interface (Typer)
│   ├── main.py    # Main CLI app
│   └── chat.py    # Chat loop handler
├── core/          # Core functionality
│   ├── agent.py   # Agent orchestrator
│   ├── session.py # Runtime session state
│   └── history.py # JSON persistence
├── provider/      # LLM abstraction
│   ├── base.py    # LLMProvider base class
│   └── providers.py
├── tools/         # Tool system
│   ├── base.py    # BaseTool interface
│   ├── registry.py
│   └── builtin_tools.py
├── frontend/      # UI abstraction
│   ├── base.py    # Frontend interface
│   └── console.py # Rich console implementation
└── utils/         # Config, logging
```

## Adding Custom Tools

```python
from picklebot.tools.base import tool

@tool(
    name="my_tool",
    description="Does something",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input text"},
        },
        "required": ["input"],
    },
)
async def my_tool(input: str) -> str:
    return f"Processed: {input}"
```

Register in `Agent` constructor or via `ToolRegistry.register()`.

## Adding LLM Providers

```python
from picklebot.provider.base import LLMProvider

class MyProvider(LLMProvider):
    provider_config_name = ["myprovider", "my_provider"]
    # Inherits default chat() via litellm
```

## Development

```bash
uv run pytest        # Run tests
uv run black .       # Format
uv run ruff check .  # Lint
uv run mypy .        # Type check
```

## License

MIT
