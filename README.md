# Pickle-Bot

A personal AI assistant with pluggable skills, built with Python.

## Features

- **Pluggable Skills System** - Easily extend functionality with custom skills
- **LLM Provider Abstraction** - Support for multiple LLM providers (Z.ai, OpenAI, Anthropic)
- **CLI Interface** - Clean command-line interface with subcommands
- **YAML Configuration** - Config-driven with system/user config split

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd pickle-bot

# Install with uv
uv sync

# Or with pip
pip install -e .
```

## Configuration

Configuration is stored in `~/.pickle-bot/`:

```
~/.pickle-bot/
├── config.system.yaml    # System defaults (shipped with app)
└── config.user.yaml      # Your overrides (optional)
```

### Example Configuration

**`~/.pickle-bot/config.system.yaml`:**
```yaml
agent:
  name: "pickle"
  system_prompt: "You are pickle-bot, a helpful AI assistant."
  behavior:
    temperature: 0.7
    max_tokens: 4096

skills:
  directory: ./skills
  builtin:
    - echo
    - get_time
    - get_system_info
  execution:
    timeout: 30
    max_concurrent: 5

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  path: logs/pickle-bot.log
  rotation: daily
  retention: 30
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
# Show help
picklebot --help

# Start interactive chat
picklebot chat

# Show agent status
picklebot status

# Use custom config directory
picklebot --config /path/to/config chat
```

### Skills Commands

```bash
# List available skills
picklebot skills list

# Show skill details
picklebot skills info <skill-name>

# Execute a skill directly
picklebot skills execute <skill-name> --args '{"param": "value"}'
```

## Built-in Skills

| Skill | Description |
|-------|-------------|
| `echo` | Echo back input text |
| `get_time` | Get current time and date |
| `get_system_info` | Get system information |

## Project Structure

```
pickle-bot/
├── src/
│   └── picklebot/
│       ├── cli/            # CLI interface
│       │   ├── main.py     # Main CLI app
│       │   ├── skills.py   # Skills subcommands
│       │   └── commands.py # Command handlers
│       ├── core/           # Core agent functionality
│       │   ├── agent.py    # Agent class
│       │   ├── config.py   # Configuration models
│       │   └── state.py    # Agent state
│       ├── llm/            # LLM provider abstraction
│       │   ├── base.py     # Base provider class
│       │   ├── factory.py  # Provider factory
│       │   └── providers.py # Provider implementations
│       ├── skills/         # Skills system
│       │   ├── base.py     # BaseSkill interface
│       │   ├── registry.py # Skill registry
│       │   └── builtin_skills.py
│       └── utils/          # Utilities
├── main.py                 # Entry point
└── pyproject.toml          # Dependencies
```

## Adding Custom Skills

Create a new skill by inheriting from `BaseSkill`:

```python
from picklebot.skills.base import BaseSkill, skill

# Option 1: Using decorator
@skill(
    name="my_skill",
    description="Does something cool",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input text"},
        },
        "required": ["input"],
    },
)
async def my_skill(input: str) -> str:
    return f"Processed: {input}"

# Option 2: Using class
class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something cool"
    parameters = {...}

    async def execute(self, **kwargs):
        return f"Result: {kwargs}"
```

Place custom skills in the `skills/` directory.

## LLM Providers

Pickle-bot supports multiple LLM providers through an abstraction layer:

- **zai** - Z.ai (GLM models)
- **openai** - OpenAI (GPT models)
- **anthropic** - Anthropic (Claude models)

To add a new provider, implement `BaseLLMProvider` and register it:

```python
from picklebot.llm.factory import register_provider
from picklebot.llm.base import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    async def chat(self, messages, tools):
        # Your implementation
        pass

register_provider("myprovider", MyProvider)
```

## Development

```bash
# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check .

# Type check
uv run mypy .
```

## License

MIT
