# Documentation Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor documentation by extracting detailed content from README.md and CLAUDE.md into feature-based docs.

**Architecture:** Create four new documentation files (configuration.md, features.md, architecture.md, extending.md), then condense README.md and CLAUDE.md to their essential purposes.

**Tech Stack:** Markdown documentation

---

## Task 1: Create docs/configuration.md

**Files:**
- Create: `docs/configuration.md`

**Step 1: Create file with header and overview**

```markdown
# Configuration Reference

Complete guide to configuring pickle-bot.

## Directory Structure

Configuration and data are stored in `~/.pickle-bot/`:

```
~/.pickle-bot/
├── config.system.yaml    # System defaults (version-controlled)
├── config.user.yaml      # User overrides (api keys, custom settings)
├── agents/               # Agent definitions
│   ├── pickle/
│   │   └── AGENT.md
│   └── cookie/
│       └── AGENT.md
├── memories/             # Long-term memory storage
│   ├── topics/           # Timeless facts about user
│   ├── projects/         # Project state and context
│   └── daily-notes/      # Day-specific events
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

## Configuration Files

### System vs User Config

Configuration uses a deep-merge pattern:

- **config.system.yaml** - Version-controlled defaults
- **config.user.yaml** - Local overrides (api keys, personal settings)

User config overrides system config at the key level. Arrays are replaced, objects are merged recursively.

### Example Configuration

**config.system.yaml:**
```yaml
default_agent: pickle
logging_path: .logs
history_path: .history
```

**config.user.yaml:**
```yaml
llm:
  provider: zai
  model: "zai/glm-4.7"
  api_key: "your-api-key"
  api_base: "https://api.z.ai/api/coding/paas/v4"

# Optional overrides
memories_path: memories
agents_path: agents
skills_path: skills
crons_path: crons
```

## Configuration Options

### LLM Settings

```yaml
llm:
  provider: zai              # Provider name (zai, openai, anthropic)
  model: "zai/glm-4.7"       # Model identifier
  api_key: "your-key"        # API key
  api_base: "https://..."    # Optional: custom API endpoint
  temperature: 0.7           # Optional: sampling temperature
  max_tokens: 4096           # Optional: max response tokens
```

### Path Configuration

All paths are relative to workspace directory (`~/.pickle-bot/` by default):

```yaml
agents_path: agents          # Agent definitions directory
skills_path: skills          # Skill definitions directory
crons_path: crons            # Cron definitions directory
memories_path: memories      # Memory storage directory
history_path: .history       # Session history directory
logging_path: .logs          # Log files directory
```

### Default Agent

```yaml
default_agent: pickle        # Agent used when no agent specified
```

## MessageBus Configuration

MessageBus enables chat via Telegram and Discord with shared conversation history.

### Basic Setup

```yaml
messagebus:
  enabled: true
  default_platform: telegram   # Required when enabled
```

### Telegram Configuration

```yaml
messagebus:
  telegram:
    enabled: true
    bot_token: "your-telegram-bot-token"
    allowed_chat_ids: ["123456789"]  # Whitelist (empty = allow all)
    default_chat_id: "123456789"     # Target for proactive messages
```

**Getting a bot token:**
1. Message @BotFather on Telegram
2. Send `/newbot` and follow instructions
3. Copy the token to config

**Getting chat IDs:**
1. Add @userinfobot to your chat
2. It will respond with the chat ID

### Discord Configuration

```yaml
messagebus:
  discord:
    enabled: true
    bot_token: "your-discord-bot-token"
    channel_id: "optional-channel-id"
    allowed_chat_ids: []             # Whitelist (empty = allow all)
    default_chat_id: ""              # Target for proactive messages
```

**Getting a bot token:**
1. Go to https://discord.com/developers/applications
2. Create new application
3. Navigate to Bot section
4. Click "Add Bot"
5. Copy the token

**Getting channel ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced)
2. Right-click channel → Copy ID

### User Whitelist

The `allowed_chat_ids` array controls who can interact with the bot:

- **Empty array `[]`** - Allow all users (public bot)
- **Non-empty `["123", "456"]`** - Only allow listed users
- Messages from non-whitelisted users are silently ignored

### Platform Routing

- **User messages** - Reply to sender's platform (Telegram → Telegram, Discord → Discord)
- **Cron messages** - Send to `default_platform` using `default_chat_id`
- **Proactive messages** - Use `post_message` tool to send to `default_chat_id`

## MessageBus Patterns

### Shared Session

All platforms share a single conversation session. This means:
- User can switch between Telegram and Discord mid-conversation
- Context carries over across platforms
- Single history file for all interactions

### Event-Driven Processing

Messages are processed sequentially via asyncio.Queue:
1. Platform receives message
2. MessageBusWorker adds to queue
3. AgentWorker picks up job
4. Agent processes and responds
5. Response routed to originating platform

### Console Logging

Server mode enables console logging by default:
```bash
uv run picklebot server
# Logs visible in terminal
```

**Step 2: Verify file exists**

Run: `ls -la docs/configuration.md`
Expected: File exists with content from Step 1

**Step 3: Commit**

```bash
git add docs/configuration.md
git commit -m "docs: add configuration reference"
```

---

## Task 2: Create docs/features.md

**Files:**
- Create: `docs/features.md`

**Step 1: Create file with agent definitions section**

```markdown
# Features Reference

Comprehensive guide to pickle-bot features.

## Agents

Agents are the core of pickle-bot. Each agent has a unique personality, system prompt, and can use different LLM models.

### Agent Definition Format

Agents are defined in `AGENT.md` files with YAML frontmatter:

```markdown
---
name: Agent Name              # Required: Display name
description: Brief desc       # Required: shown in subagent_dispatch tool
provider: openai              # Optional: override shared LLM provider
model: gpt-4                  # Optional: override shared model
temperature: 0.7              # Optional: sampling temperature (0-2)
max_tokens: 4096              # Optional: max response tokens
allow_skills: true            # Optional: enable skill tool (default: false)
---

System prompt goes here...

You can use multiple paragraphs and markdown formatting.
```

### Multi-Agent Support

Pickle-bot supports multiple agents for different purposes:

- **Pickle** - General-purpose assistant (default agent)
- **Cookie** - Memory management specialist
- Custom agents - Create your own for specialized tasks

Each agent maintains its own configuration and system prompt.

### Agent-Specific LLM Settings

Agents can override global LLM settings:

```markdown
---
name: Code Reviewer
provider: anthropic
model: claude-3-opus-20240229
temperature: 0.3
---
```

This allows using different models for different tasks (e.g., cheaper model for simple tasks, more capable model for complex reasoning).

## Subagent Dispatch

Agents can delegate specialized work to other agents through the `subagent_dispatch` tool.

### How It Works

1. Calling agent invokes: `subagent_dispatch(agent_id="reviewer", task="Review this code")`
2. Target agent receives task with fresh session
3. Target agent processes and returns result
4. Calling agent receives JSON: `{"result": "...", "session_id": "uuid"}`

### Automatic Tool Registration

The `subagent_dispatch` tool is automatically registered when:
- Multiple agents exist in the system
- The calling agent is excluded from the dispatchable list (prevents infinite loops)

### Use Cases

- **Pickle → Cookie** - Delegate memory storage and retrieval
- **Code agent → Review agent** - Separate implementation from review
- **Research agent → Writer agent** - Separate research from writing

### Session Persistence

Each dispatch creates a separate session that persists to history. This allows:
- Reviewing subagent conversations later
- Resuming interrupted work
- Auditing agent interactions

## Skills

Skills are user-defined capabilities loaded on-demand by the LLM. Unlike tools (always available), skills are loaded only when needed.

### Skill Definition Format

Skills are defined in `SKILL.md` files:

```markdown
---
name: Brainstorming
description: Turn ideas into fully formed designs through collaborative dialogue
---

# Brainstorming Ideas Into Designs

[Detailed skill instructions...]

## Process
1. Understand the idea
2. Ask clarifying questions
3. Propose approaches
4. Present design
```

### Enabling Skills

Add `allow_skills: true` to agent frontmatter:

```markdown
---
name: Pickle
allow_skills: true
---
```

This registers a `skill` tool that the agent can call to:
1. List available skills
2. Load a specific skill
3. Follow skill instructions

### When to Create Skills

Create a skill when:
- Workflow has multiple steps
- Requires domain knowledge
- Benefits from structured approach
- Will be reused across conversations

Create a tool when:
- Simple, single operation
- Technical/programmatic action
- Always available (not context-dependent)

## Crons

Cron jobs run scheduled agent invocations automatically.

### Cron Definition Format

```markdown
---
name: Inbox Check
agent: pickle              # Which agent to run
schedule: "*/15 * * * *"   # Cron syntax
---

Check my inbox and summarize unread messages.
```

### Schedule Syntax

Uses standard cron syntax: `minute hour day month weekday`

Examples:
- `"*/15 * * * *"` - Every 15 minutes
- `"0 9 * * *"` - Daily at 9 AM
- `"0 */2 * * *"` - Every 2 hours

### Server Mode

Cron jobs require server mode:

```bash
uv run picklebot server
```

The server runs CronWorker which:
1. Checks for due jobs every 60 seconds
2. Dispatches jobs to agent queue
3. Executes sequentially (one job at a time)

### Cron Requirements

- **Minimum granularity:** 5 minutes (prevent spam)
- **Fresh session:** Each run starts with empty context
- **Sequential execution:** Jobs processed one at a time
- **Silent frontend:** No console output during execution

### Proactive Messaging

Cron jobs can send messages to user via `post_message` tool:
- Messages sent to `default_platform` → `default_chat_id`
- Useful for notifications, reminders, status updates
- Requires MessageBus to be enabled

## Memory System

Long-term memories are managed by the Cookie agent (a specialized subagent).

### Organizational Structure

Memory files are organized along three axes:

**topics/** - Timeless facts about the user
```
preferences.md      # User preferences
relationships.md    # Important relationships
identity.md         # Core identity information
```

**projects/** - Project state and context
```
pickle-bot.md       # Pickle-bot project status
work-project.md     # Work project details
```

**daily-notes/** - Day-specific events
```
2024-02-20.md       # Events from Feb 20
2024-02-21.md       # Events from Feb 21
```

### Memory Flows

**Real-Time Storage:**
1. User shares information during conversation
2. Pickle recognizes it as memorable
3. Pickle dispatches to Cookie agent
4. Cookie writes to appropriate memory file

**Scheduled Capture:**
1. Daily cron runs at 2 AM
2. Reviews conversations from past day
3. Extracts missed memories
4. Stores in appropriate files

**On-Demand Retrieval:**
1. User asks about past information
2. Pickle dispatches to Cookie
3. Cookie searches memory files
4. Returns relevant context

### Memory File Format

Memory files use simple markdown:

```markdown
# User Preferences

- Prefers dark mode in all applications
- Works best in the morning (9 AM - 12 PM)
- Likes concise, action-oriented responses
- Uses vim for text editing

## Programming

- Primary language: Python
- Framework: FastAPI
- Testing: pytest
```

## MessageBus

MessageBus enables chat via Telegram and Discord with shared conversation history.

### Platform Support

- **Telegram** - Full support via python-telegram-bot
- **Discord** - Full support via discord.py

### Shared Session Architecture

All platforms share a single AgentSession:
- User can switch platforms mid-conversation
- Context and history carry over
- Single source of truth for conversation state

### Platform Routing

Messages are routed based on origin:

**User-initiated:**
- User sends message on Telegram
- Agent responds on Telegram
- Platform preserved in context

**Agent-initiated (crons):**
- Cron job completes
- Agent sends to `default_platform`
- Uses `default_chat_id` from config

**Proactive messaging:**
- Agent calls `post_message` tool
- Message sent to `default_platform` → `default_chat_id`
- Useful for notifications and alerts

### User Whitelist

Control who can interact with the bot:

```yaml
telegram:
  allowed_chat_ids: ["123456789"]
```

- **Empty list** - Allow all users
- **Non-empty list** - Only allow listed users
- Non-whitelisted messages are silently ignored

### Event-Driven Processing

Messages flow through queue-based system:

1. Platform receives message → creates context
2. MessageBusWorker validates whitelist
3. Job added to asyncio.Queue
4. AgentWorker picks up job
5. Agent processes sequentially
6. Response routed to originating platform

This ensures messages are processed one at a time, preventing race conditions.

## Heartbeat & Continuous Work

Pickle-bot can work continuously on projects through the heartbeat cron pattern.

### Heartbeat Cron

Create a cron that checks on active projects:

```markdown
---
name: Heartbeat
agent: pickle
schedule: "*/30 * * * *"
---

## Active Tasks

- [ ] Check on project X progress
- [ ] Monitor build status for project Y

## Completed

<!-- Move completed tasks here -->
```

### Workflow

1. **Assign project** - User asks Pickle to monitor project
2. **Cookie creates memory** - `memories/projects/{name}.md` created
3. **Add to heartbeat** - Pickle adds task to heartbeat CRON.md
4. **Periodic checks** - Heartbeat fires every 30 minutes
5. **Act if needed** - Pickle checks project state, takes action
6. **Remove when done** - User asks to stop, task removed

### Benefits

- Agents work autonomously between user interactions
- Continuous monitoring without user presence
- Automatic notifications on important events
- Task tracking in CRON.md body

### Example Tasks

- Monitor CI/CD pipeline status
- Check for new pull requests
- Review overnight test results
- Validate deployment health
- Track deadline approaches


**Step 2: Verify file exists**

Run: `ls -la docs/features.md`
Expected: File exists with content from Step 1

**Step 3: Commit**

```bash
git add docs/features.md
git commit -m "docs: add features reference"
```

---

## Task 3: Create docs/architecture.md

**Files:**
- Create: `docs/architecture.md`

**Step 1: Create file with architecture overview**

```markdown
# Architecture Reference

Detailed technical architecture for pickle-bot.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      User Interface                      │
│                   (CLI / Telegram / Discord)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                        Agent                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Session  │  │  Tools   │  │   LLM    │             │
│  │ (State)  │  │Registry  │  │Provider  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   SharedContext                          │
│  Config | Frontend | ToolRegistry | Loaders             │
└─────────────────────────────────────────────────────────┘
```

**Core Flow:**
1. User sends message via CLI/Telegram/Discord
2. Agent receives message in session context
3. Agent builds context from session history
4. Agent calls LLM with tools available
5. LLM responds with tool calls
6. Agent executes tool calls
7. Agent sends results back to LLM
8. LLM generates final response
9. Response sent to user via frontend

## Component Architecture

### Agent (core/agent.py)

The main orchestrator that handles chat loops and LLM interaction.

**Responsibilities:**
- Receive AgentDef with configuration
- Build context from session history
- Present tools to LLM via function calling
- Execute tool calls via ToolRegistry
- Stream responses to frontend
- Handle errors gracefully

**Key Methods:**
- `new_session(mode)` - Create fresh session
- `resume_session(session_id)` - Load existing session
- `chat(message, frontend)` - Process user message

### AgentDef (core/agent_def.py)

Immutable definition loaded from AGENT.md files.

**Attributes:**
- `id` - Unique identifier (folder name)
- `name` - Display name
- `description` - Brief description
- `system_prompt` - Full system prompt
- `llm` - LLM configuration (provider, model, etc.)
- `allow_skills` - Whether skill tool is enabled

### AgentLoader (core/agent_loader.py)

Discovers and loads agent definitions.

**Methods:**
- `load(agent_id)` - Load specific agent
- `discover_agents()` - Find all available agents

**Uses:** `def_loader.parse_definition()` for YAML frontmatter parsing

### AgentSession (core/session.py)

Runtime state for a conversation. Manages in-memory message list and persists to HistoryStore.

**Attributes:**
- `session_id` - Unique identifier
- `agent_id` - Which agent owns this session
- `mode` - CHAT or JOB
- `messages` - List of HistoryMessage objects

**Key Methods:**
- `chat(message, frontend)` - Process message in session context
- `save()` - Persist to HistoryStore

**Lifecycle:**
- Created via `agent.new_session()` or `agent.resume_session()`
- Persists across tool calls within conversation
- Saved to disk after each message

### SharedContext (core/context.py)

Container for shared resources passed to Agent and workers.

**Attributes:**
- `config` - Config object
- `frontend` - Frontend interface
- `tool_registry` - ToolRegistry instance
- `agent_loader` - AgentLoader instance
- `skill_loader` - SkillLoader instance
- `cron_loader` - CronLoader instance

**Purpose:** Avoid passing individual components everywhere.

### SkillLoader (core/skill_loader.py)

Discovers and loads SKILL.md files.

**Methods:**
- `load(skill_id)` - Load specific skill
- `discover_skills()` - Find all available skills

**Used by:** `create_skill_tool()` to build the skill tool

### CronLoader (core/cron_loader.py)

Discovers and loads CRON.md files with schedule definitions.

**Methods:**
- `load(cron_id)` - Load specific cron
- `discover_crons()` - Find all cron jobs

**Returns:** List of CronDef objects with schedule and prompt

### MessageBus (messagebus/base.py)

Abstract generic base for platform-specific message handling.

**Type Parameters:**
- `T` - Platform context type (TelegramContext, DiscordContext)

**Key Methods:**
- `is_allowed(context)` - Check whitelist
- `reply(content, context)` - Reply to originating chat
- `post(content, target=None)` - Post to default chat

**Implementations:**
- `TelegramBus[TelegramContext]`
- `DiscordBus[DiscordContext]`

### HistoryStore (core/history.py)

JSON file-based persistence for conversation history.

**Directory:** `~/.pickle-bot/history/sessions/`

**Files:**
- `index.json` - Fast session listing
- `{session_id}.json` - Individual session messages

**HistoryMessage:**
- `from_message()` - Convert from litellm Message
- `to_message()` - Convert to litellm Message

**Bidirectional conversion ensures** compatibility with LLM providers.

### LLMProvider (provider/base.py)

Abstract base for LLM providers using litellm.

**Key Method:**
- `chat(messages, tools)` - Send messages to LLM

**Subclasses only need:**
- `provider_config_name` - List of provider names

**Auto-registration:** Provider registers itself when class is defined.

**Built-in Providers:**
- ZaiProvider (zai)
- OpenAIProvider (openai)
- AnthropicProvider (anthropic)

### ToolRegistry (tools/registry.py)

Registers tools and generates schemas for LiteLLM function calling.

**Methods:**
- `register(tool)` - Add tool to registry
- `get_schemas()` - Generate OpenAI function schemas
- `execute(name, args)` - Execute tool by name

**Registration:**
- Use `@tool` decorator (recommended)
- Inherit from `BaseTool` (advanced)

### def_loader (utils/def_loader.py)

Shared utilities for parsing markdown files with YAML frontmatter.

**Functions:**
- `parse_definition(path, model_class)` - Parse single definition
- `discover_definitions(path, model_class)` - Find all definitions

**Returns:** Pydantic model instance with frontmatter fields + markdown body

**Raises:**
- `DefNotFoundError` - Definition folder/file doesn't exist
- `InvalidDefError` - Definition file is malformed

### Frontend (frontend/base.py)

Abstract UI interface for presenting agent responses.

**Key Methods:**
- `show(content)` - Display agent message
- `show_transient(content)` - Display temporary status (tool calls)
- `reply(content)` - Send reply to user

**Implementations:**
- `ConsoleFrontend` - Rich terminal output
- `SilentFrontend` - No output (cron jobs)
- `MessageBusFrontend` - Platform-specific output

## Server Architecture

Worker-based architecture for `picklebot server` mode.

### Worker Base Class (workers/base.py)

```python
class Worker(ABC):
    def __init__(self, context: SharedContext):
        self.context = context
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def run(self) -> None:
        """Main worker loop. Runs until cancelled."""
        pass

    def start(self) -> asyncio.Task:
        """Start worker as asyncio Task."""
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        """Gracefully stop worker."""
        if self._task:
            self._task.cancel()
            await self._task
```

### Job Flow

```
┌─────────────────┐     ┌─────────────────┐
│ MessageBusWorker│     │   CronWorker    │
│                 │     │                 │
│ Telegram ──────►│     │  Find due ─────►│
│ Discord ───────►│     │  jobs           │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │     ┌─────────────────▼────────┐
         └────►│    asyncio.Queue[Job]    │
               └─────────────────┬────────┘
                                 │
                       ┌─────────▼──────────┐
                       │    AgentWorker     │
                       │                    │
                       │  Execute agent ───►│
                       │  chat              │
                       └─────────┬──────────┘
                                 │
                                 ▼
                          Frontend.reply()
```

### AgentWorker (workers/agent_worker.py)

Executes agent jobs from queue sequentially.

**Responsibilities:**
- Pick up jobs from asyncio.Queue
- Load agent definition
- Create or resume session
- Execute agent chat
- Handle errors and requeue on crash

**Crash Recovery:**
- Failed jobs are requeued with `message = "."`
- Worker restarts and picks up job
- Session resumes from HistoryStore
- LLM sees history + "." message, naturally continues

### CronWorker (workers/cron_worker.py)

Finds due cron jobs, dispatches to agent queue.

**Responsibilities:**
- Wake every 60 seconds
- Check all cron schedules
- Find jobs that are due
- Create Job objects with fresh sessions
- Dispatch to agent queue

**Always creates new sessions** (no memory between runs).

### MessageBusWorker (workers/messagebus_worker.py)

Ingests messages from platforms, dispatches to agent queue.

**Responsibilities:**
- Own global session shared across platforms
- Start platform listeners (Telegram, Discord)
- Validate whitelist on incoming messages
- Create Job objects with platform context
- Dispatch to agent queue

**Platform Routing:**
- User messages → reply to sender's platform
- Maintains platform context through MessageBusFrontend

### Server (workers/server.py)

Orchestrates workers with health monitoring.

**Responsibilities:**
- Create workers based on config
- Start all workers as asyncio tasks
- Monitor worker health every 5 seconds
- Auto-restart crashed workers
- Graceful shutdown on interrupt

**Worker Setup:**
- Always: AgentWorker, CronWorker
- Optional: MessageBusWorker (if messagebus.enabled)

## Project Structure

```
src/picklebot/
├── cli/                    # CLI interface
│   ├── main.py            # Main CLI app with Typer
│   ├── chat.py            # Chat loop handler
│   └── server.py          # Server command
├── core/                   # Core functionality
│   ├── agent.py           # Agent orchestrator
│   ├── agent_def.py       # Agent definition model
│   ├── agent_loader.py    # Load AGENT.md files
│   ├── session.py         # Runtime session state
│   ├── history.py         # JSON persistence
│   ├── context.py         # Shared context container
│   ├── skill_loader.py    # Load SKILL.md files
│   └── cron_loader.py     # Load CRON.md files
├── workers/                # Server workers
│   ├── base.py            # Worker base class
│   ├── server.py          # Server orchestrator
│   ├── agent_worker.py    # Execute agent jobs
│   ├── messagebus_worker.py # Handle platform messages
│   └── cron_worker.py     # Schedule cron jobs
├── messagebus/             # Message bus abstraction
│   ├── base.py            # MessageBus interface
│   ├── telegram_bus.py    # Telegram implementation
│   └── discord_bus.py     # Discord implementation
├── provider/               # LLM abstraction
│   ├── base.py            # LLMProvider base
│   └── providers.py       # Built-in providers
├── tools/                  # Tool system
│   ├── base.py            # BaseTool interface
│   ├── registry.py        # Tool registration
│   ├── builtin_tools.py   # read, write, edit, bash
│   ├── skill_tool.py      # Skill loading tool
│   ├── subagent_tool.py   # Subagent dispatch tool
│   └── post_message_tool.py # Proactive messaging
├── frontend/               # UI abstraction
│   ├── base.py            # Frontend interface
│   └── console.py         # Rich console
└── utils/                  # Utilities
    ├── config.py          # Config loading
    ├── logging.py         # Logging setup
    └── def_loader.py      # Definition parsing
```

## Key Design Decisions

### Why Workers Instead of Threads?

- **Asyncio native** - All components already async
- **No GIL limitations** - I/O bound work doesn't need threads
- **Simpler state** - No thread synchronization needed
- **Queue-based** - Natural message passing pattern

### Why asyncio.Queue for Job Routing?

- **Sequential execution** - Prevents race conditions
- **Crash recovery** - Jobs remain in queue on worker crash
- **Backpressure** - Natural flow control
- **Type safety** - Typed Job objects flow through queue

### Why YAML Frontmatter for Definitions?

- **Human readable** - Easy to edit manually
- **Git friendly** - Text files, good for version control
- **Extensible** - Add new fields without code changes
- **Self-documenting** - Markdown body provides context

### Why Separate System and User Config?

- **Version control** - System config can be committed
- **Secrets safety** - User config excluded from git
- **Overrides** - Users can customize without touching defaults
- **Distribution** - Defaults ship with code, user config is local
```

**Step 2: Verify file exists**

Run: `ls -la docs/architecture.md`
Expected: File exists with content from Step 1

**Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture reference"
```

---

## Task 4: Create docs/extending.md

**Files:**
- Create: `docs/extending.md`

**Step 1: Create file with extension guide**

```markdown
# Extending Pickle-Bot

Guide to extending and customizing pickle-bot.

## Adding Custom Tools

Tools are functions the LLM can call to perform actions.

### Using @tool Decorator

Simplest way to create a tool:

```python
from picklebot.tools.base import tool

@tool(
    name="my_tool",
    description="Does something useful",
    parameters={
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Input text to process"
            },
            "count": {
                "type": "integer",
                "description": "Number of times to process"
            }
        },
        "required": ["input"]
    },
)
async def my_tool(input: str, count: int = 1) -> str:
    """Process input text and return result."""
    result = input * count
    return f"Processed: {result}"
```

### Parameter Schema

Use OpenAI function calling schema format:

```python
parameters={
    "type": "object",
    "properties": {
        "param_name": {
            "type": "string",  # string, integer, number, boolean, array
            "description": "What this parameter does"
        }
    },
    "required": ["param_name"]  # List of required parameters
}
```

### Tool Function Requirements

- **Async function** - Must be `async def`
- **Type hints** - Help with validation
- **Return string** - All tools return string responses
- **No side effects in signature** - Parameters come from LLM

### Registration

Tools are registered at startup:

```python
# In SharedContext initialization
registry = ToolRegistry()
registry.register(my_tool)
```

Or inject later:

```python
context.tool_registry.register(my_tool)
```

### Using BaseTool Class

For more control, inherit from BaseTool:

```python
from picklebot.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {...}

    async def execute(self, **kwargs) -> str:
        # Custom logic here
        return "result"
```

Use BaseTool when:
- Need stateful tool
- Complex initialization required
- Multiple related operations

## Adding LLM Providers

Support new LLM providers by inheriting from LLMProvider.

### Minimum Implementation

```python
from picklebot.provider.base import LLMProvider

class MyProvider(LLMProvider):
    # List of provider names (for config matching)
    provider_config_name = ["myprovider", "my_provider"]

    # That's it! Inherits chat() from base class
```

The base class handles:
- Message formatting
- Tool schema conversion
- Response parsing
- Error handling

### Provider Registration

Providers auto-register when class is defined:

```python
# Just defining the class registers it
class MyProvider(LLMProvider):
    provider_config_name = ["myprovider"]
```

Use in config:

```yaml
llm:
  provider: myprovider
  model: "myprovider/model-name"
  api_key: "your-key"
```

### Custom Chat Implementation

Override `chat()` for custom behavior:

```python
class MyProvider(LLMProvider):
    provider_config_name = ["myprovider"]

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None
    ) -> Message:
        # Custom implementation
        # Must return Message object
        return Message(...)
```

## Creating Skills

Skills are markdown files with instructions loaded on-demand.

### Skill File Format

Create `~/.pickle-bot/skills/my-skill/SKILL.md`:

```markdown
---
name: My Skill
description: Brief description for LLM to decide whether to load
---

# My Skill

Detailed instructions for the skill...

## When to Use

- Scenario 1
- Scenario 2

## Process

1. Step one
2. Step two
3. Step three

## Examples

Example usage scenarios...
```

### Skill Best Practices

**Clear description:** Help LLM decide when to load
- Good: "Turn ideas into fully formed designs through dialogue"
- Bad: "A skill for things"

**Structured instructions:** Use headings, lists, code blocks
- Process steps
- Decision criteria
- Examples

**Single purpose:** One skill, one job
- Split complex skills into multiple
- Combine simple related skills

### Enabling Skills

Add to agent frontmatter:

```markdown
---
name: My Agent
allow_skills: true
---
```

The `skill` tool will be automatically registered.

### When to Create Skills vs Tools

**Create a skill when:**
- Multi-step workflow
- Requires domain knowledge
- Structured approach needed
- Will be reused

**Create a tool when:**
- Single operation
- Technical/programmatic action
- Always available
- Simple input/output

## Creating Agents

Define specialized agents for different tasks.

### Agent File Format

Create `~/.pickle-bot/agents/my-agent/AGENT.md`:

```markdown
---
name: Code Reviewer
description: Reviews code for quality and best practices
provider: anthropic
model: claude-3-opus-20240229
temperature: 0.3
max_tokens: 4096
---

You are a code review specialist...

Your responsibilities:
1. Review code for bugs
2. Check for best practices
3. Suggest improvements

Be thorough but concise...
```

### Agent Configuration

**Required fields:**
- `name` - Display name
- `description` - Brief description (shown in subagent_dispatch)

**Optional fields:**
- `provider` - Override global LLM provider
- `model` - Override global model
- `temperature` - Sampling temperature (0-2)
- `max_tokens` - Max response length
- `allow_skills` - Enable skill tool

### System Prompt Guidelines

**Be specific:**
- Define role and responsibilities
- Set expectations for behavior
- Provide decision criteria

**Be concise:**
- Agents have token limits
- Use bullet points
- Avoid repetition

**Include context:**
- When to use this agent
- What inputs to expect
- What outputs to produce

### Agent Examples

**Memory Manager (Cookie):**
```markdown
---
name: Cookie
description: Manages long-term memories
---

You manage the user's long-term memory...

Store memories in:
- topics/ - Timeless facts
- projects/ - Project state
- daily-notes/ - Day-specific events
```

**Code Reviewer:**
```markdown
---
name: Code Reviewer
description: Reviews code for quality
temperature: 0.3
---

You review code for:
- Bugs and errors
- Security issues
- Performance problems
- Best practices
```

## Creating Cron Jobs

Schedule automated tasks with cron jobs.

### Cron File Format

Create `~/.pickle-bot/crons/my-cron/CRON.md`:

```markdown
---
name: Daily Summary
agent: pickle
schedule: "0 9 * * *"
---

Generate a daily summary of:
- Calendar events for today
- Pending tasks
- Important emails
```

### Schedule Syntax

Standard cron format: `minute hour day month weekday`

**Examples:**
- `"*/15 * * * *"` - Every 15 minutes
- `"0 9 * * *"` - Daily at 9 AM
- `"0 */2 * * *"` - Every 2 hours
- `"0 9 * * 1"` - Every Monday at 9 AM

### Cron Requirements

- **Minimum granularity:** 5 minutes
- **Fresh session:** No memory between runs
- **Sequential execution:** One job at a time
- **Server mode:** Requires `picklebot server`

### Cron Prompt Tips

**Be specific:**
- List exact tasks
- Define success criteria
- Specify output format

**Use proactive messaging:**
```markdown
---
name: Build Monitor
agent: pickle
schedule: "*/5 * * * *"
---

Check if build is failing.
If failing, use post_message tool to notify me.
```

**Keep it simple:**
- One responsibility per cron
- Clear success/failure conditions
- Actionable output

## Frontend Customization

Create custom frontends for different output modes.

### Frontend Interface

```python
from picklebot.frontend.base import Frontend

class MyFrontend(Frontend):
    async def show(self, content: str) -> None:
        """Display agent message."""
        # Your implementation

    async def show_transient(self, content: str) -> None:
        """Display temporary status."""
        # Your implementation

    async def reply(self, content: str) -> None:
        """Send reply to user."""
        # Your implementation
```

### Frontend Types

**ConsoleFrontend:** Rich terminal output
- Syntax highlighting
- Progress indicators
- Markdown rendering

**SilentFrontend:** No output
- Used for cron jobs
- Background tasks

**MessageBusFrontend:** Platform-specific output
- Routes to Telegram/Discord
- Platform context preserved

### Custom Frontend Example

```python
class LoggingFrontend(Frontend):
    def __init__(self, log_file: str):
        self.log_file = log_file

    async def show(self, content: str) -> None:
        with open(self.log_file, 'a') as f:
            f.write(f"AGENT: {content}\n")

    async def reply(self, content: str) -> None:
        with open(self.log_file, 'a') as f:
            f.write(f"REPLY: {content}\n")
        print(content)  # Also show in console
```
```

**Step 2: Verify file exists**

Run: `ls -la docs/extending.md`
Expected: File exists with content from Step 1

**Step 3: Commit**

```bash
git add docs/extending.md
git commit -m "docs: add extending guide"
```

---

## Task 5: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Replace README.md with minimal version**

```markdown
# Pickle-Bot

A personal AI assistant with pluggable tools and multi-agent support.

## Quick Start

```bash
git clone <repo-url>
cd pickle-bot
uv sync
uv run picklebot chat
```

## What It Does

- **Multi-Agent AI** - Specialized agents (Pickle for general tasks, Cookie for memory)
- **Multiple Platforms** - Chat via CLI, Telegram, or Discord
- **Scheduled Tasks** - Run cron jobs automatically in server mode
- **Long-Term Memory** - Persistent context across conversations
- **Extensible** - Add custom tools, skills, and agents

## Documentation

- **[Configuration](docs/configuration.md)** - Setup and configuration guide
- **[Features](docs/features.md)** - Agents, skills, crons, memory, and messaging
- **[Architecture](docs/architecture.md)** - Technical architecture details
- **[Extending](docs/extending.md)** - How to add tools, providers, and agents

## Development

```bash
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
```

## License

MIT
```

**Step 2: Verify README is minimal**

Run: `wc -l README.md`
Expected: < 40 lines

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: condense README to minimal quickstart"
```

---

## Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Replace CLAUDE.md with essential patterns**

```markdown
# CLAUDE.md

Essential context for working in pickle-bot codebase.

## Commands

```bash
uv run picklebot chat              # Interactive chat with default agent
uv run picklebot chat -a cookie    # Use specific agent
uv run picklebot server            # Start server (crons + messagebus)
uv run pytest                      # Run tests
uv run black . && uv run ruff check .  # Format + lint
```

## Architecture Overview

**Entry Points:**
- `cli/` - Typer commands (chat, server)
- `workers/` - Server mode workers (AgentWorker, CronWorker, MessageBusWorker)

**Core Flow:**
```
Agent receives message → loads tools → calls LLM → executes tool calls → response
```

**Key Files:**
- `core/agent.py` - Main orchestrator
- `core/session.py` - Runtime state + history
- `workers/server.py` - Worker orchestration
- `tools/registry.py` - Tool registration
- `messagebus/base.py` - Platform abstraction

## Critical Patterns

### Worker Architecture

All workers inherit from `Worker` base class. Jobs flow through `asyncio.Queue` to AgentWorker for sequential execution.

```
MessageBusWorker/CronWorker → Queue → AgentWorker → Execute
```

See [docs/architecture.md](docs/architecture.md) for details.

### Definition Loading

All definitions (agents, skills, crons) use `def_loader.py` utilities:

```python
from picklebot.utils.def_loader import parse_definition, discover_definitions
from picklebot.core.agent_def import AgentDef

# Load single definition
agent_def = parse_definition(path, AgentDef)

# Discover all definitions
agents = discover_definitions(agents_path, AgentDef)
```

Raises:
- `DefNotFoundError` - Definition folder/file doesn't exist
- `InvalidDefError` - Definition file is malformed

### Message Conversion

`HistoryMessage` ↔ litellm `Message` conversion:

```python
# Message → HistoryMessage (for persistence)
history_msg = HistoryMessage.from_message(message)

# HistoryMessage → Message (for LLM context)
message = history_msg.to_message()
```

### Tool Registration

Use `@tool` decorator or inherit `BaseTool`. Registered in `ToolRegistry`, schemas auto-generated for LiteLLM.

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

### Config Loading

Deep merge: `config.system.yaml` (defaults) ← `config.user.yaml` (overrides)

Paths are relative to workspace and auto-resolved:

```python
agents_path: Path = Path("agents")   # resolves to workspace/agents
skills_path: Path = Path("skills")   # resolves to workspace/skills
```

## Key Conventions

- **Workers** - Single responsibility, communicate via queues, restart on crash
- **Sessions** - One per conversation, persisted to `~/.pickle-bot/history/`
- **Tools** - Async functions, return strings, registered at startup
- **MessageBus** - Platform-agnostic with typed context (TelegramContext, DiscordContext)
- **Errors** - Custom exceptions in `utils/def_loader.py`
- **Frontend** - Abstract interface, platform-specific implementations

## What Goes Where

- **Configuration details** → [docs/configuration.md](docs/configuration.md)
- **Full feature docs** → [docs/features.md](docs/features.md)
- **Component details** → [docs/architecture.md](docs/architecture.md)
- **Extension guide** → [docs/extending.md](docs/extending.md)
```

**Step 2: Verify CLAUDE.md is concise**

Run: `wc -l CLAUDE.md`
Expected: < 120 lines

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: condense CLAUDE.md to essential patterns"
```

---

## Task 7: Verify Documentation

**Files:**
- Verify: `docs/` directory

**Step 1: Check all docs exist**

Run: `ls -la docs/*.md`
Expected: All four new docs + existing plans

**Step 2: Check line counts**

Run: `wc -l README.md CLAUDE.md docs/*.md`
Expected:
- README.md < 40 lines
- CLAUDE.md < 120 lines
- docs/configuration.md ~150 lines
- docs/features.md ~250 lines
- docs/architecture.md ~200 lines
- docs/extending.md ~150 lines

**Step 3: Verify links in CLAUDE.md**

Run: `grep -o "\[.*\](docs/.*\.md)" CLAUDE.md`
Expected: Links to all four new docs

---

## Task 8: Final Commit

**Step 1: Review all changes**

Run: `git status`
Expected: All documentation changes committed

**Step 2: Verify no uncommitted changes**

Run: `git diff`
Expected: No output (all committed)

**Step 3: Create summary commit (if needed)**

If any files remain uncommitted:

```bash
git add -A
git commit -m "docs: complete documentation refactor"
```

---

## Success Criteria

- [ ] README.md < 40 lines
- [ ] CLAUDE.md < 120 lines
- [ ] docs/configuration.md exists with config reference
- [ ] docs/features.md exists with feature docs
- [ ] docs/architecture.md exists with architecture details
- [ ] docs/extending.md exists with extension guide
- [ ] All links in CLAUDE.md work
- [ ] All changes committed
- [ ] No duplicate content
- [ ] Each doc has single clear purpose
