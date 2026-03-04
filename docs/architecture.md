# Architecture Reference

Technical architecture for pickle-bot's event-driven system.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     External Interfaces                      │
│              CLI / Telegram / Discord / HTTP API             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       EventBus                               │
│            Central pub/sub event distribution                │
│    Persist OutboundEvent • Recover on restart               │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ AgentWorker  │  │DeliveryWorker│  │WebSocketWrkr │
│              │  │              │  │              │
│ Run agent    │  │ Deliver to   │  │ Stream to    │
│ chat loop    │  │ platforms    │  │ WS clients   │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Core Flow:**
1. External source (CLI/Telegram/Discord/Cron) creates `InboundEvent`
2. EventBus publishes event to subscribers
3. AgentWorker receives event, runs agent chat
4. AgentWorker emits `OutboundEvent` with response
5. DeliveryWorker receives OutboundEvent, delivers to platform
6. EventBus persists OutboundEvent until delivery confirmed

## Event System

### Event Types (`core/events.py`)

```python
@dataclass
class Event:
    session_id: str
    agent_id: str
    source: EventSource
    content: str
    timestamp: float

@dataclass
class InboundEvent(Event):
    """External work entering the system."""
    retry_count: int = 0

@dataclass
class OutboundEvent(Event):
    """Agent responses to deliver to platforms."""
    error: str | None = None

@dataclass
class DispatchEvent(Event):
    """Internal agent-to-agent delegation."""
    parent_session_id: str = ""
    retry_count: int = 0

@dataclass
class DispatchResultEvent(Event):
    """Result of a dispatched job."""
    error: str | None = None
```

### EventSource Hierarchy

Typed event origins with platform-specific data:

```python
class EventSource(ABC):
    _namespace: ClassVar[str]  # Registry key
    _registry: ClassVar[dict[str, type["EventSource"]]]

    @property
    def is_platform(self) -> bool: ...
    @property
    def is_agent(self) -> bool: ...
    @property
    def is_cron(self) -> bool: ...

    @classmethod
    def from_string(cls, s: str) -> "EventSource": ...
```

**Implementations:**

| Source | Namespace | Format |
|--------|-----------|--------|
| `AgentEventSource` | `agent` | `agent:{agent_id}` |
| `CronEventSource` | `cron` | `cron:{cron_id}` |
| `CliEventSource` | `platform-cli` | `platform-cli:{user_id}` |
| `TelegramEventSource` | `platform-telegram` | `platform-telegram:{user_id}:{chat_id}` |
| `DiscordEventSource` | `platform-discord` | `platform-discord:{user_id}:{channel_id}` |

### EventBus (`core/eventbus.py`)

Central pub/sub with persistence:

```python
class EventBus(Worker):
    def subscribe(self, event_class: type[E], handler: Callable[[E], Awaitable[None]]) -> None
    async def publish(self, event: Event) -> None
    async def run(self) -> None  # Process queue, dispatch to subscribers
    def ack(self, event: Event) -> None  # Delete persisted event after delivery
```

**Persistence:**
- OutboundEvents saved to disk before delivery
- Atomic write (tmp + fsync + rename)
- Recovery on startup from crash

## Workers

### AgentWorker (`server/agent_worker.py`)

Executes agent chat sessions:

- Subscribes to `InboundEvent` and `DispatchEvent`
- Loads agent, creates or resumes session
- Runs agent chat loop
- Emits `OutboundEvent` or `DispatchResultEvent`

### CronWorker (`server/cron_worker.py`)

Scheduled job emitter:

- Wakes every 60 seconds
- Checks cron schedules
- Emits `InboundEvent` for due jobs

### MessageBusWorker (`server/messagebus_worker.py`)

Platform message ingester:

- Runs Telegram/Discord listeners
- Validates whitelist
- Emits `InboundEvent` for incoming messages

### DeliveryWorker (`server/delivery_worker.py`)

Message delivery:

- Subscribes to `OutboundEvent`
- Routes to appropriate MessageBus
- Calls `bus.reply()` or `bus.post()`
- Acknowledges event on success

### WebSocketWorker (`server/websocket_worker.py`)

Real-time event streaming:

- Subscribes to all events
- Streams to connected WebSocket clients

## Routing (`core/routing.py`)

Routes event sources to agents:

```python
@dataclass
class Binding:
    agent: str
    value: str  # Regex pattern
    tier: int   # Specificity (0=exact, 1=regex, 2=wildcard)

class RoutingTable:
    def resolve(self, source: str) -> str:
        """Return agent_id for source, fallback to default_agent."""
```

**Config:**
```yaml
routing:
  bindings:
    - agent: pickle
      value: "platform-telegram:.*"
    - agent: cookie
      value: "platform-discord:.*"
```

## MessageBus (`messagebus/`)

Platform abstraction with EventSource:

```python
class MessageBus(ABC, Generic[T]):
    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @abstractmethod
    async def run(self, on_message: Callable[[str, T], Awaitable[None]]) -> None: ...

    @abstractmethod
    async def reply(self, content: str, source: T) -> None: ...

    @abstractmethod
    async def post(self, content: str, target: str | None = None) -> None: ...
```

**Implementations:**
- `TelegramBus[TelegramEventSource]`
- `DiscordBus[DiscordEventSource]`
- `CliBus[CliEventSource]`

## Agent System

### Agent (`core/agent.py`)

Factory for sessions:

```python
class Agent:
    def __init__(self, agent_def: AgentDef, context: SharedContext): ...
    def new_session(self, source: str, ...) -> AgentSession: ...
    def resume_session(self, session_id: str) -> AgentSession: ...
```

### AgentSession (`core/agent.py`)

Runtime conversation state:

```python
@dataclass
class AgentSession:
    session_id: str
    agent_id: str
    source: str
    messages: list[Message]
    tools: ToolRegistry

    async def chat(self, message: str) -> str: ...
```

### AgentDef (`core/agent_loader.py`)

Immutable definition from AGENT.md:

```python
class AgentDef(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool
```

## Commands System (`core/commands/`)

Slash commands for user interactions:

```python
class Command(ABC):
    name: str
    aliases: list[str]
    description: str

    @abstractmethod
    def execute(self, args: str, ctx: SharedContext) -> str: ...
```

## SharedContext (`core/context.py`)

DI container for shared resources:

```python
@dataclass
class SharedContext:
    config: Config
    eventbus: EventBus
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    messagebus_buses: list[MessageBus]
```

## History (`core/history.py`)

JSON-based conversation persistence:

```yaml
~/.pickle-bot/history/
├── index.json           # Session listing
└── sessions/
    └── {session_id}.json
```

**HistoryMessage:**
- `from_message()` - Convert from litellm Message
- `to_message()` - Convert to litellm Message

## Provider Architecture

### LLMProvider (`provider/llm/base.py`)

```python
class LLMProvider(ABC):
    @classmethod
    def from_config(cls, config: LLMConfig) -> "LLMProvider": ...
    async def chat(self, messages: list[Message], tools: list[dict]) -> tuple[str, list[LLMToolCall]]: ...
```

**Built-in:** ZaiProvider, OpenAIProvider

### WebSearchProvider (`provider/web_search/base.py`)

```python
class WebSearchProvider(ABC):
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...
```

**Built-in:** BraveSearchProvider

### WebReadProvider (`provider/web_read/base.py`)

```python
class WebReadProvider(ABC):
    async def read(self, url: str) -> ReadResult: ...
```

**Built-in:** Crawl4AIProvider

## Project Structure

```
src/picklebot/
├── cli/                    # CLI interface
│   ├── main.py            # Typer app
│   ├── chat.py            # Interactive chat
│   ├── server.py          # Server command
│   └── onboarding/        # Setup wizard
├── core/                   # Core domain
│   ├── agent.py           # Agent + AgentSession
│   ├── agent_loader.py    # AgentDef loader
│   ├── events.py          # Event types + EventSource
│   ├── eventbus.py        # Pub/sub distribution
│   ├── routing.py         # Source routing
│   ├── context.py         # SharedContext DI
│   ├── history.py         # Conversation persistence
│   ├── skill_loader.py    # Skill loader
│   ├── cron_loader.py     # Cron loader
│   └── commands/          # Slash commands
├── server/                 # Server workers
│   ├── server.py          # Orchestration
│   ├── worker.py          # Base Worker class
│   ├── agent_worker.py    # Agent execution
│   ├── cron_worker.py     # Scheduled jobs
│   ├── delivery_worker.py # Message delivery
│   ├── messagebus_worker.py # Platform ingestion
│   └── websocket_worker.py # WebSocket streaming
├── messagebus/            # Platform implementations
│   ├── base.py            # MessageBus ABC
│   ├── cli_bus.py         # CLI (CliEventSource)
│   ├── telegram_bus.py    # Telegram (TelegramEventSource)
│   └── discord_bus.py     # Discord (DiscordEventSource)
├── provider/              # External providers
│   ├── llm/               # LLM providers
│   ├── web_search/        # Web search
│   └── web_read/          # Web content reading
├── tools/                 # Agent tools
│   ├── registry.py        # Tool registration
│   ├── base.py            # BaseTool
│   ├── builtin_tools.py   # read, write, edit, bash
│   ├── skill_tool.py      # Skill loading
│   ├── subagent_tool.py   # Agent dispatch
│   ├── post_message_tool.py # Proactive messaging
│   ├── websearch_tool.py  # Web search
│   └── webread_tool.py    # Web reading
├── api/                   # HTTP API
│   ├── app.py             # FastAPI factory
│   ├── deps.py            # Dependency injection
│   ├── schemas.py         # Request/response models
│   └── routers/           # REST endpoints
└── utils/                 # Utilities
    ├── config.py          # Configuration
    ├── logging.py         # Logging setup
    └── def_loader.py      # Definition parsing
```

## Workspace Structure

The workspace uses a layered prompt architecture where system prompts are assembled from multiple markdown files at runtime.

### Layered Prompt Assembly

Prompts are built in layers (see `core/prompt_builder.py`):

1. **Identity** - AGENT.md body (agent-specific instructions)
2. **Soul** - SOUL.md (personality, optional)
3. **Bootstrap** - BOOTSTRAP.md + AGENTS.md + cron list
4. **Runtime** - Agent ID + timestamp
5. **Channel** - Platform name hint

### Workspace Directory Layout

```
default_workspace/
├── config.user.yaml          # User configuration (created by onboarding)
├── config.runtime.yaml       # Runtime state (optional, auto-managed)
├── BOOTSTRAP.md              # Workspace context (paths, structure, file purposes)
├── AGENTS.md                 # Agent registry with dispatch guidelines
├── agents/                   # Agent definitions
│   ├── pickle/
│   │   ├── AGENT.md          # Agent config and instructions
│   │   └── SOUL.md           # Agent personality
│   └── cookie/
│       ├── AGENT.md
│       └── SOUL.md
├── skills/                   # Reusable skills
│   └── {name}/
│       └── SKILL.md
├── crons/                    # Scheduled tasks
└── memories/                 # Persistent memory storage
    ├── topics/               # Timeless facts
    ├── projects/             # Project-specific context
    └── daily-notes/          # Day-specific events (YYYY-MM-DD.md)
```

### Layered Files

#### AGENT.md (Required)
Agent-specific configuration and instructions:
- Frontmatter: name, description, llm settings, allow_skills flag
- Body: Capabilities, behavioral guidelines, operational instructions
- Example location: `agents/pickle/AGENT.md`

```yaml
---
name: Pickle
description: A friendly cat assistant for daily tasks
allow_skills: true
llm:
  temperature: 0.7
  max_tokens: 4096
---

You are Pickle, a friendly cat assistant...

## Capabilities
- Answer questions and explain concepts
- Help with coding, debugging, and technical tasks
...
```

#### SOUL.md (Optional)
Agent personality layer:
- Character traits and tone
- Concatenated with AGENT.md at runtime as "Personality" section
- No workspace or dispatch references (those go in BOOTSTRAP/AGENTS.md)
- Example location: `agents/pickle/SOUL.md`

```markdown
# Personality

You are Pickle, a friendly cat assistant. Be warm and genuinely helpful with subtle cat mannerisms...
```

#### BOOTSTRAP.md (Workspace-Level)
Shared workspace context:
- Template variables: `{{workspace}}`, `{{skills_path}}`, etc.
- Directory structure documentation
- File purpose explanations
- Workspace-specific conventions
- Example location: `default_workspace/BOOTSTRAP.md`

```markdown
# Workspace Guide

## Paths
- Workspace: `{{workspace}}`
- Skills: `{{skills_path}}`
...
```

#### AGENTS.md (Workspace-Level)
Agent registry and dispatch guidelines:
- Lists all available agents with descriptions
- Explains when and how to use `subagent_dispatch`
- Provides dispatch patterns and examples
- Example location: `default_workspace/AGENTS.md`

```markdown
# Available Agents

| Agent | Description |
|-------|-------------|
| pickle | Default agent for general conversations |
| cookie | Memory manager for store/retrieve operations |

## Dispatching Tasks
Use `subagent_dispatch` to delegate tasks to specialized agents...
```

### Prompt Assembly Flow

```python
class PromptBuilder:
    def build(self, session: AgentSession) -> str:
        layers = []

        # Layer 1: Identity from AGENT.md
        layers.append(session.agent.agent_def.agent_md)

        # Layer 2: Soul from SOUL.md (optional)
        if session.agent.agent_def.soul_md:
            layers.append(f"## Personality\n\n{session.agent.agent_def.soul_md}")

        # Layer 3: Bootstrap context
        # Combines BOOTSTRAP.md + AGENTS.md + cron list
        layers.append(self._load_bootstrap_context())

        # Layer 4: Runtime context
        layers.append(f"## Runtime\n\nAgent: {agent_id}\nTime: {timestamp}")

        # Layer 5: Channel hint
        layers.append(f"You are responding via {platform_name}.")

        return "\n\n".join(layers)
```

### Design Benefits

**Separation of Concerns:**
- Agent behavior in AGENT.md
- Agent personality in SOUL.md
- Workspace context in BOOTSTRAP.md
- Agent registry in AGENTS.md

**Maintainability:**
- Personality can be tweaked without touching instructions
- Workspace structure documented in one place
- Agent registry centralized for easy updates

**Reusability:**
- Same workspace bootstrap for all agents
- Personality optional (not all agents need it)
- Template variables for path flexibility

## Design Decisions

### Why Event-Driven Architecture?

- **Decoupling** - Workers don't know about each other
- **Persistence** - OutboundEvents survive crashes
- **Testability** - Subscribe to events in tests
- **Extensibility** - Add new workers by subscribing

### Why Typed EventSource?

- **Type safety** - Platform-specific data in typed fields
- **No serialization complexity** - Each source knows how to serialize
- **Clean API** - `source.chat_id` instead of `context.chat_id`

### Why Workers Instead of Threads?

- **Asyncio native** - All components already async
- **No GIL limitations** - I/O bound work doesn't need threads
- **Simpler state** - No thread synchronization needed
