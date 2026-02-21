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

- **Pickle -> Cookie** - Delegate memory storage and retrieval
- **Code agent -> Review agent** - Separate implementation from review
- **Research agent -> Writer agent** - Separate research from writing

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
- Messages sent to `default_platform` -> `default_chat_id`
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
- Message sent to `default_platform` -> `default_chat_id`
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

1. Platform receives message -> creates context
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
