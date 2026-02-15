# Pickle-Bot

A personal AI assistant with pluggable tools, built with Python.

## Features

- **Multi-Agent Support** - Define multiple agents with different prompts and settings
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
├── agents/               # Agent definitions
│   └── pickle/
│       └── AGENT.md
└── history/              # Session persistence
    ├── sessions/
    └── index.json
```

**`~/.pickle-bot/config.system.yaml`:**
```yaml
default_agent: pickle
logging_path: .logs
history_path: .history
```

**`~/.pickle-bot/config.user.yaml`:**
```yaml
llm:
  provider: zai
  model: "zai/glm-4.7"
  api_key: "your-api-key"
  api_base: "https://api.z.ai/api/coding/paas/v4"
```

**`~/.pickle-bot/agents/pickle/AGENT.md`:**
```markdown
---
name: Pickle
temperature: 0.7
max_tokens: 4096
---

You are pickle-bot, a helpful AI assistant.
```

### Agent Definition Format

Agents are defined in `AGENT.md` files with YAML frontmatter:

```markdown
---
name: Agent Name              # Required
provider: openai              # Optional: override shared LLM provider
model: gpt-4                  # Optional: override shared model
temperature: 0.7              # Optional: sampling temperature
max_tokens: 4096              # Optional: max response tokens
---

System prompt goes here...
```

## Usage

```bash
picklebot chat              # Start interactive chat (uses default_agent)
picklebot chat --agent name # Use specific agent
picklebot chat -a name      # Shorthand
picklebot --help            # Show help
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
│   ├── agent_def.py   # Agent definition model
│   ├── agent_loader.py # Agent file loader
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
