# Configuration Reference

Complete guide to configuring pickle-bot.

## Directory Structure

Configuration and data are stored in `~/.pickle-bot/`:

```
~/.pickle-bot/
├── config.user.yaml      # User configuration (created by onboarding)
├── config.runtime.yaml   # Runtime state (optional, internal, auto-managed)
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

### Two-Layer Config Merge

Configuration uses a deep-merge pattern with two layers:

- **config.user.yaml** - User configuration (required fields: `llm`, `default_agent`)
- **config.runtime.yaml** - Runtime state (optional, internal, managed by application)

Merge order: user <- runtime. Runtime config overrides user config for overlapping keys.

### Initial Setup

Run `picklebot init` to create your configuration interactively:

```bash
uv run picklebot init
```

This creates `config.user.yaml` with your LLM settings and default agent.

### Updating Config Programmatically

Use the `set_user()` and `set_runtime()` methods:

```python
# User preferences (written to config.user.yaml)
ctx.config.set_user("default_agent", "cookie")

# Runtime state (written to config.runtime.yaml)
ctx.config.set_runtime("current_session_id", "abc123")
```

### Example Configuration

**config.user.yaml:**
```yaml
default_agent: pickle

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

### History Settings

Control how conversation history is managed:

```yaml
chat_max_history: 50         # Max messages for LLM context in chat mode
job_max_history: 500         # Max messages for LLM context in job mode (crons)
max_history_file_size: 500   # Max messages per history chunk file
```

- **chat_max_history** - Limits messages sent to LLM during interactive chat (smaller for faster responses)
- **job_max_history** - Limits messages sent to LLM during cron jobs (larger for background work)
- **max_history_file_size** - Controls how history is chunked on disk (separate from LLM context limits)

### HTTP API Settings

Enable the REST API for SDK-like access:

```yaml
api:
  enabled: true              # Enable HTTP API (default: true)
  host: "127.0.0.1"          # Bind address (default: 127.0.0.1)
  port: 8000                 # Port number (default: 8000)
```

The API runs as part of `picklebot server` when enabled. See [Features](features.md#http-api) for available endpoints.

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
    allowed_user_ids: ["123456789"]  # Whitelist (empty = allow all)
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
    allowed_user_ids: []             # Whitelist (empty = allow all)
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

The `allowed_user_ids` array controls who can interact with the bot:

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
