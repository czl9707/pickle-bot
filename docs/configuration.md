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

Configuration uses a two-layer merge pattern:

- **config.user.yaml** - User configuration (required fields: `llm`, `default_agent`)
- **config.runtime.yaml** - Runtime state (optional, internal, managed by application)

Merge order: user <- runtime. Runtime config overrides user config for overlapping keys.

### Initial Setup

Run `picklebot init` to create your configuration interactively:

```bash
uv run picklebot init
```

This creates `config.user.yaml` with your LLM settings and default agent.

## Complete Configuration Reference

Below is a comprehensive example showing all available options with inline comments:

```yaml
# === USER-MANAGED (edit freely) ===

default_agent: pickle

llm:
  provider: zai                    # Provider name (zai, openai, anthropic)
  model: "zai/glm-4.7"             # Model identifier
  api_key: "your-api-key"          # Your API key
  api_base: "https://..."          # Optional: custom API endpoint
  temperature: 0.7                 # Optional: sampling temperature (0-2)
  max_tokens: 4096                 # Optional: max response tokens

# Web Tools (optional - enables websearch and webread tools)
websearch:
  provider: brave
  api_key: "your-brave-api-key"    # Get from https://brave.com/search/api/

webread:
  provider: crawl4ai               # No API key needed, uses local browser

# Paths (optional, defaults shown)
agents_path: agents
skills_path: skills
crons_path: crons
memories_path: memories
history_path: .history
logging_path: .logs

# History limits
chat_max_history: 50               # Max messages for LLM context in chat mode
job_max_history: 500               # Max messages for LLM context in job mode (crons)
max_history_file_size: 500         # Max messages per history chunk file

# HTTP API (omit section to disable)
api:
  host: "127.0.0.1"
  port: 8000

# MessageBus (optional - enables Telegram/Discord)
messagebus:
  enabled: true
  default_platform: telegram       # Required if enabled: "telegram" or "discord"

  telegram:
    enabled: true
    bot_token: "your-telegram-bot-token"
    allowed_user_ids: []           # Empty = allow all, or list user IDs
    default_chat_id: ""            # Target for proactive messages

  discord:
    enabled: false
    bot_token: ""
    channel_id: ""
    allowed_user_ids: []
    default_chat_id: ""

# === RUNTIME-MANAGED (auto-updated by application) ===
# Do not edit these manually - they are managed internally

# current_session_id: "uuid"       # Current session tracking
# messagebus.telegram.sessions: {} # Maps user_id -> session_id
# messagebus.discord.sessions: {}  # Maps user_id -> session_id
```

### MessageBus Platform Setup

**Telegram:**
1. Message @BotFather on Telegram
2. Send `/newbot` and follow instructions
3. Copy the token to `messagebus.telegram.bot_token`
4. Add @userinfobot to your chat to get the chat ID

**Discord:**
1. Go to https://discord.com/developers/applications
2. Create new application
3. Navigate to Bot section, click "Add Bot"
4. Copy the token to `messagebus.discord.bot_token`
5. Enable Developer Mode in Discord (User Settings -> Advanced)
6. Right-click channel -> Copy ID for `channel_id`

### User Whitelist

The `allowed_user_ids` array controls who can interact with the bot:

- **Empty array `[]`** - Allow all users (public bot)
- **Non-empty `["123", "456"]`** - Only allow listed users
- Messages from non-whitelisted users are silently ignored

### Platform Routing

- **User messages** - Reply to sender's platform (Telegram -> Telegram, Discord -> Discord)
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
