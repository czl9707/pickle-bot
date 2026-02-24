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

### AgentSession (core/agent.py)

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

### Provider Architecture

Modular provider system for LLM, web search, and web read capabilities.

#### LLMProvider (provider/llm/base.py)

Abstract base for LLM providers using litellm.

**Key Method:**
- `chat(messages, tools)` - Send messages to LLM

**Subclasses only need:**
- `provider_config_name` - List of provider names

**Auto-registration:** Provider registers itself when class is defined.

**Built-in Providers (provider/llm/providers.py):**
- ZaiProvider (zai)
- OpenAIProvider (openai)

#### WebSearchProvider (provider/web_search/base.py)

Abstract base for web search providers.

**Models:**
- `SearchResult` - Unified search result with title, url, snippet

**Key Methods:**
- `search(query, max_results)` - Execute search, return list of SearchResult
- `from_config(config)` - Factory method to instantiate configured provider

**Implementations:**
- `BraveSearchProvider` (provider/web_search/brave.py) - Brave Search API

#### WebReadProvider (provider/web_read/base.py)

Abstract base for web content reading providers.

**Models:**
- `ReadResult` - Unified read result with content, metadata

**Key Methods:**
- `read(url)` - Fetch and parse web content, return ReadResult
- `from_config(config)` - Factory method to instantiate configured provider

**Implementations:**
- `Crawl4AIProvider` (provider/web_read/crawl4ai.py) - Crawl4AI-based reader

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
- `discover_definitions(path, model_class)` - Find all definitions in directory
- `write_definition(id, frontmatter, content, base_path, filename)` - Write definition with frontmatter

**Returns:** Pydantic model instance with frontmatter fields + markdown body

**Raises:**
- `DefNotFoundError` - Definition folder/file doesn't exist
- `InvalidDefError` - Definition file is malformed

### Message Conversion

`HistoryMessage` <-> litellm `Message` conversion for persistence and LLM context:

```python
from picklebot.core.history import HistoryMessage

# Message -> HistoryMessage (for persistence)
history_msg = HistoryMessage.from_message(message)

# HistoryMessage -> Message (for LLM context)
message = history_msg.to_message()
```

Bidirectional conversion ensures compatibility with all LLM providers via litellm.

### Config Loading (utils/config.py)

Two-layer deep merge: `config.user.yaml` <- `config.runtime.yaml`

- **config.user.yaml** - User configuration (required fields: `llm`, `default_agent`). Created by onboarding.
- **config.runtime.yaml** - Runtime state (optional, internal only, managed by application)

**Programmatic updates:**

```python
# User preferences (persists to config.user.yaml)
ctx.config.set_user("default_agent", "cookie")

# Runtime state (persists to config.runtime.yaml)
ctx.config.set_runtime("current_session_id", "abc123")
```

**Deep merge:** Nested objects merge recursively; scalar values are replaced.

### HTTP API Internals

FastAPI-based REST API using `SharedContext` via dependency injection:

```python
from picklebot.api.deps import get_context
from picklebot.core.context import SharedContext
from fastapi import Depends

@router.get("/{agent_id}")
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)):
    return ctx.agent_loader.load(agent_id)
```

**Creating definitions via API:**

```python
from picklebot.utils.def_loader import write_definition

frontmatter = {"name": "My Agent", "temperature": 0.7}
write_definition("my-agent", frontmatter, "System prompt...", agents_path, "AGENT.md")
```

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

### Worker Base Class (server/base.py)

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

### AgentWorker (server/agent_worker.py)

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

### CronWorker (server/cron_worker.py)

Finds due cron jobs, dispatches to agent queue.

**Responsibilities:**
- Wake every 60 seconds
- Check all cron schedules
- Find jobs that are due
- Create Job objects with fresh sessions
- Dispatch to agent queue

**Always creates new sessions** (no memory between runs).

### MessageBusWorker (server/messagebus_worker.py)

Ingests messages from platforms, dispatches to agent queue.

**Responsibilities:**
- Own global session shared across platforms
- Start platform listeners (Telegram, Discord)
- Validate whitelist on incoming messages
- Create Job objects with platform context
- Dispatch to agent queue

**Platform Routing:**
- User messages -> reply to sender's platform
- Maintains platform context through MessageBusFrontend

### Server (server/server.py)

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
│   ├── server.py          # Server command
│   └── onboarding/        # Onboarding wizard
│       ├── wizard.py      # Main wizard orchestrator
│       ├── steps.py       # Individual wizard steps
│       └── __init__.py
├── core/                   # Core functionality
│   ├── agent.py           # Agent orchestrator
│   ├── agent_def.py       # Agent definition model
│   ├── agent_loader.py    # Load AGENT.md files
│   ├── history.py         # JSON persistence
│   ├── context.py         # Shared context container
│   ├── skill_loader.py    # Load SKILL.md files
│   └── cron_loader.py     # Load CRON.md files
├── server/                 # Server workers
│   ├── base.py            # Worker base class
│   ├── server.py          # Server orchestrator
│   ├── agent_worker.py    # Execute agent jobs
│   ├── messagebus_worker.py # Handle platform messages
│   └── cron_worker.py     # Schedule cron jobs
├── messagebus/             # Message bus abstraction
│   ├── base.py            # MessageBus interface
│   ├── telegram_bus.py    # Telegram implementation
│   └── discord_bus.py     # Discord implementation
├── provider/               # Provider abstraction
│   ├── llm/               # LLM providers
│   │   ├── base.py        # LLMProvider base
│   │   └── providers.py   # Built-in providers (zai, openai)
│   ├── web_search/        # Web search providers
│   │   ├── base.py        # WebSearchProvider base, SearchResult model
│   │   └── brave.py       # Brave Search implementation
│   └── web_read/          # Web read providers
│       ├── base.py        # WebReadProvider base, ReadResult model
│       └── crawl4ai.py    # Crawl4AI implementation
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

### Why YAML Frontmatter for Definitions?

- **Uniform Format** - Agents and Skills has metadata as frontmatter 
- **Human readable** - Easy to edit manually
- **Git friendly** - Text files, good for version control
- **Extensible** - Add new fields without code changes
- **Self-documenting** - Markdown body provides context
