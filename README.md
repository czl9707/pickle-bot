# Pickle-Bot

A personal AI assistant with pluggable tools, built with Python.

## Features

- **Multi-Agent Support** - Define multiple agents with different prompts and settings
- **Subagent Dispatch** - Delegate specialized work to other agents through tool calls
- **Long-Term Memory** - Persistent memory via Cookie agent with topic and time-based organization
- **Message Bus Support** - Chat via Telegram and Discord with shared conversation history
- **Skill System** - On-demand capability loading for specialized tasks
- **Pluggable Tools System** - Function calling with custom tools
- **Cron Jobs** - Scheduled agent invocations via server mode
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
│   ├── pickle/
│   │   └── AGENT.md
│   └── cookie/
│       └── AGENT.md           # Memory management agent
├── memories/             # Long-term memory storage
│   ├── topics/                # Timeless facts
│   └── daily-notes/           # Day-specific events
├── skills/               # Skill definitions
│   └── brainstorming/
│       └── SKILL.md
├── crons/                # Cron job definitions
│   └── inbox-check/
│       └── CRON.md
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
memories_path: memories        # Optional: override memory storage location

# Optional: Enable message bus (Telegram and/or Discord)
messagebus:
  enabled: true
  default_platform: telegram   # Required when enabled
  telegram:
    enabled: true
    bot_token: "your-telegram-bot-token"
    allowed_user_ids: ["123456789"]  # Whitelist: only these users can message
    default_user_id: "123456789"     # Target for agent-initiated messages
  discord:
    enabled: false
    bot_token: "your-discord-bot-token"
    channel_id: "optional-channel-id"
    allowed_user_ids: []
    default_user_id: ""
```

## Usage

```bash
picklebot chat              # Start interactive chat (uses default_agent)
picklebot chat --agent name # Use specific agent
picklebot chat -a name      # Shorthand
picklebot -w /path chat     # Use custom workspace directory
picklebot --help            # Show help
```

### Server Mode

Run pickle-bot as a 24/7 server for scheduled cron jobs and message bus:

```bash
picklebot server            # Start server with default workspace
picklebot server -w /path   # Use custom workspace
```

The server runs two components:
- **CronExecutor** - Executes scheduled cron jobs
- **MessageBusExecutor** - Handles incoming messages from Telegram/Discord (when configured)

#### Cron Jobs

The server reads cron jobs from `~/.pickle-bot/crons/[job-id]/CRON.md`:

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

**Cron job requirements:**
- Minimum granularity: 5 minutes
- Fresh session per run (no memory between runs)
- Sequential execution (one job at a time)
- Responses sent to `default_platform` when messagebus is enabled

#### Message Bus

When message bus is enabled, the server also handles incoming messages from Telegram and Discord:

- **Shared conversation** - Single session across all platforms
- **Event-driven** - Queue-based sequential message processing
- **Platform routing** - User messages reply to sender's platform, cron messages use `default_platform`
- **Console logging** - Logs visible in terminal while server runs

**User Whitelist:**
Configure `allowed_user_ids` per platform to restrict who can message the bot. Messages from non-whitelisted users are silently ignored. An empty list allows all users.

**Proactive Messaging:**
The `post_message` tool allows agents to send messages proactively (e.g., cron job notifications, task completion alerts). Messages are sent to the `default_user_id` on the `default_platform`.

See `docs/message-bus-setup.md` for Telegram and Discord bot setup instructions.

## Definition Formats

### Agent Definition

Agents are defined in `AGENT.md` files with YAML frontmatter:

```markdown
---
name: Agent Name              # Required
description: Brief desc       # Required: shown in subagent_dispatch tool
provider: openai              # Optional: override shared LLM provider
model: gpt-4                  # Optional: override shared model
temperature: 0.7              # Optional: sampling temperature
max_tokens: 4096              # Optional: max response tokens
allow_skills: true            # Optional: enable skill tool
---

System prompt goes here...
```

### Subagent Dispatch

Agents can delegate work to other agents via the `subagent_dispatch` tool. When multiple agents exist, an agent can dispatch a task to another specialized agent:

```
Agent A calls: subagent_dispatch(agent_id="reviewer", task="Review this code", context="...")
Returns: {"result": "...", "session_id": "uuid"}
```

Each dispatch creates a separate session that persists to history. The calling agent is automatically excluded from the dispatchable agents list (prevents infinite loops).

### Skill Definition

Skills are user-defined capabilities loaded on-demand by the LLM:

```markdown
---
name: Brainstorming
description: Turn ideas into fully formed designs through collaborative dialogue
---

# Brainstorming Ideas Into Designs

[Skill instructions...]
```

To enable skills on an agent, add `allow_skills: true` to its frontmatter. The LLM can then call the `skill` tool to load and use available skills.

### Cron Definition

Cron jobs run scheduled agent invocations:

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read` | Read file contents |
| `write` | Write content to a file |
| `edit` | Replace text in a file |
| `bash` | Execute shell commands |
| `skill` | Load and invoke a specialized skill (when enabled) |
| `subagent_dispatch` | Delegate work to another agent (when other agents exist) |
| `post_message` | Send a message to the user via default platform (when messagebus enabled) |

## Project Structure

```
src/picklebot/
├── cli/           # CLI interface (Typer)
│   ├── main.py    # Main CLI app
│   ├── chat.py    # Chat loop handler
│   └── server.py  # Cron server
├── core/          # Core functionality
│   ├── agent.py       # Agent orchestrator
│   ├── agent_def.py   # Agent definition model
│   ├── agent_loader.py
│   ├── session.py     # Runtime session state
│   ├── history.py     # JSON persistence
│   ├── context.py     # Shared context container
│   ├── skill_loader.py
│   ├── cron_loader.py
│   ├── cron_executor.py
│   └── messagebus_executor.py
├── messagebus/    # Message bus abstraction
│   ├── base.py        # MessageBus abstract interface
│   ├── telegram_bus.py
│   └── discord_bus.py
├── provider/      # LLM abstraction
│   ├── base.py    # LLMProvider base class
│   └── providers.py
├── tools/         # Tool system
│   ├── base.py    # BaseTool interface
│   ├── registry.py
│   ├── builtin_tools.py
│   ├── skill_tool.py
│   ├── subagent_tool.py
│   └── post_message_tool.py
├── frontend/      # UI abstraction
│   ├── base.py    # Frontend interface
│   └── console.py # Rich console implementation
└── utils/         # Config, logging, def_loader
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
