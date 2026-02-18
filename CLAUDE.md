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
├── cli/           # Typer CLI (main.py, chat.py, server.py)
├── core/          # Agent, AgentSession, AgentDef, loaders, executors
├── messagebus/    # Message bus abstraction (base.py, telegram_bus.py, discord_bus.py)
├── provider/      # LLM provider abstraction (base.py, providers.py)
├── tools/         # Tool system (base.py, registry.py, builtin_tools.py, skill_tool.py, subagent_tool.py, post_message_tool.py)
├── frontend/      # UI abstraction (base.py, console.py)
└── utils/         # Config, logging, def_loader
```

### Key Components

**Agent** (`core/agent.py`): Main orchestrator that handles chat loops, tool calls, and LLM interaction. Receives `AgentDef`, builds context from session history, executes tool calls via ToolRegistry.

**AgentDef** (`core/agent_def.py`): Loaded agent definition containing id, name, description, system_prompt, llm config, and `allow_skills` flag. Created by `AgentLoader` from AGENT.md files.

**AgentLoader** (`core/agent_loader.py`): Parses AGENT.md files with YAML frontmatter using `def_loader` utilities. Has `load(agent_id)` and `discover_agents()` methods. Raises `DefNotFoundError` or `InvalidDefError` on failures.

**AgentSession** (`core/session.py`): Runtime state for a conversation. Manages in-memory message list and persists to HistoryStore. Async context manager.

**SharedContext** (`core/context.py`): Container for shared resources (config, frontend, tool registry) passed to Agent and CronExecutor.

**SkillLoader** (`core/skill_loader.py`): Discovers and loads SKILL.md files. Used by `create_skill_tool()` to build the skill tool.

**CronLoader** (`core/cron_loader.py`): Discovers and loads CRON.md files with schedule definitions.

**CronExecutor** (`core/cron_executor.py`): Runs scheduled cron jobs. Loops every 60 seconds, executes due jobs sequentially with fresh sessions.

**MessageBusExecutor** (`core/messagebus_executor.py`): Handles incoming messages from messaging platforms. Uses queue-based sequential processing with a shared AgentSession across all platforms. Responses route back to sender's platform.

**MessageBus** (`messagebus/base.py`): Abstract generic base with platform-specific context. Key methods: `is_allowed(context)`, `reply(content, context)`, `post(content, target=None)`. Implementations: `TelegramBus[TelegramContext]`, `DiscordBus[DiscordContext]`.

**HistoryStore** (`core/history.py`): JSON file-based persistence. Directory: `~/.pickle-bot/history/sessions/` with an `index.json` for fast session listing. `HistoryMessage` has `from_message()` and `to_message()` methods for litellm Message conversion.

**LLMProvider** (`provider/base.py`): Abstract base using litellm. Subclasses only need to set `provider_config_name` for auto-registration. Built-in: ZaiProvider, OpenAIProvider, AnthropicProvider.

**ToolRegistry** (`tools/registry.py`): Registers tools and generates schemas for LiteLLM function calling. Use `@tool` decorator or inherit from `BaseTool`.

**def_loader** (`utils/def_loader.py`): Shared utilities for parsing markdown files with YAML frontmatter. Provides `parse_definition()` and `discover_definitions()` functions used by all loaders.

**Frontend** (`frontend/base.py`): Abstract UI interface. `ConsoleFrontend` uses Rich for terminal output. Key method: `show_transient()` displays temporary status during tool calls.

### Error Classes

All loaders use unified exceptions from `utils/def_loader.py`:

- **DefNotFoundError**: Definition folder or file doesn't exist
- **InvalidDefError**: Definition file is malformed

### Configuration

Stored in `~/.pickle-bot/`:

- `config.system.yaml` - System defaults (default_agent, paths)
- `config.user.yaml` - User overrides (llm settings, deep-merged)
- `agents/` - Agent definitions (`[name]/AGENT.md`)
- `skills/` - Skill definitions (`[name]/SKILL.md`)
- `crons/` - Cron definitions (`[name]/CRON.md`)
- `messagebus` - Message bus config (Telegram, Discord, default_platform)

Pydantic models in `utils/config.py`. Load via `Config.load(workspace_dir)`.

Config paths are relative to workspace and auto-resolved:
```python
agents_path: Path = Path("agents")   # resolves to workspace/agents
skills_path: Path = Path("skills")   # resolves to workspace/skills
crons_path: Path = Path("crons")     # resolves to workspace/crons
memories_path: Path = Path("memories")  # resolves to workspace/memories
```

### Agent Definitions

Agents are defined in `~/.pickle-bot/agents/[name]/AGENT.md`:

```markdown
---
name: Agent Display Name
description: Brief description shown in subagent_dispatch tool
provider: openai        # Optional: override shared LLM
model: gpt-4            # Optional: override shared LLM
temperature: 0.7
max_tokens: 4096
allow_skills: true      # Optional: enable skill tool
---

You are a helpful assistant...
```

Load agents via `AgentLoader`:
```python
loader = AgentLoader(config.agents_path, config.llm)
agent_def = loader.load("agent-name")
```

### Skill System

Skills are user-defined capabilities loaded on-demand by the LLM. Defined in `~/.pickle-bot/skills/[name]/SKILL.md`:

```markdown
---
name: Skill Display Name
description: Brief description for LLM to decide whether to load
---

# Skill Name

Instructions for the skill...
```

When `allow_skills: true` in an agent, a "skill" tool is registered that presents available skills and loads content on demand.

### Cron System

Cron jobs run scheduled agent invocations. Defined in `~/.pickle-bot/crons/[name]/CRON.md`:

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

Start the server with `picklebot server`. Jobs run sequentially with fresh sessions (no memory between runs).

### MessageBus System

Message bus enables chat via Telegram and Discord with shared conversation history. Configuration in `~/.pickle-bot/config.user.yaml`:

```yaml
messagebus:
  enabled: true
  default_platform: telegram  # Required when enabled
  telegram:
    enabled: true
    bot_token: "your-token"
    allowed_chat_ids: ["123456789"]  # Whitelist for incoming messages
    default_chat_id: "123456789"     # Target for agent-initiated messages
  discord:
    enabled: false
    bot_token: "your-token"
    channel_id: "optional-id"
    allowed_chat_ids: []
    default_chat_id: ""
```

**Architecture:**
- Event-driven with `asyncio.Queue` for sequential message processing
- Single shared `AgentSession` across all platforms
- Platform routing: user messages → reply to sender's platform, cron messages → `default_platform`
- `MessageBus.from_config()` factory creates bus instances with inline imports to avoid circular dependencies

**Chat Whitelist:**
- `allowed_chat_ids` filters incoming messages per platform
- Empty list allows all chats; non-empty list restricts to listed IDs
- Non-whitelisted messages are silently ignored (logged at INFO level)

**Post Message Tool:**
- `post_message_tool.py` provides `create_post_message_tool()` factory
- Tool sends messages to `default_chat_id` on `default_platform`
- Only registered when messagebus is enabled with valid config
- Useful for cron job notifications and proactive alerts

**Implementation:**
- `MessageBusExecutor` runs alongside `CronExecutor` in server mode
- Each platform implements `MessageBus` abstract interface with typed context
- `reply(content, context)` sends to the context's originating chat
- `post(content, target=None)` sends to `default_chat_id` if target not specified
- Console logging enabled in server mode via `setup_logging(config, console_output=True)`

### Memory System

Long-term memories are managed by the Cookie agent (a subagent). Cookie stores memories in markdown files with two organizational axes:

- **topics/** - Timeless facts (user preferences, project knowledge)
- **daily-notes/** - Day-specific events and decisions (YYYY-MM-DD.md)

Memory flows:
1. Real-time storage - Pickle dispatches to cookie during conversations
2. Scheduled capture - Daily cron at 2AM extracts missed memories
3. On-demand retrieval - Pickle dispatches to query relevant memories

Cookie uses existing tools (read, write, edit) to manage memory files. No special tools required.

### Subagent Dispatch System

Agents can delegate specialized work to other agents through the `subagent_dispatch` tool. The tool is automatically registered when other dispatchable agents exist.

**How it works:**
1. `create_subagent_dispatch_tool()` factory builds a tool with dynamic enum of dispatchable agents
2. Calling agent is excluded from the enum (prevents recursive dispatch)
3. Dispatch creates a new session that persists to history
4. Returns JSON with `result` and `session_id` fields

**Tool schema:**
```python
subagent_dispatch(
    agent_id: str,      # ID of target agent (enum of available agents)
    task: str,          # Task for the subagent to perform
    context: str = ""   # Optional context information
) -> str  # JSON: {"result": "...", "session_id": "..."}
```

Implementation in `tools/subagent_tool.py`. Uses `SilentFrontend` for subagent execution.

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
