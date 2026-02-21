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
