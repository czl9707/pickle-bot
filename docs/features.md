# Features Reference

Guide to pickle-bot features. See [Architecture](architecture.md) for implementation details.

## Agents

Each agent has a unique personality, system prompt, and LLM settings.

**Default agents:**
- **Pickle** - General-purpose assistant
- **Cookie** - Memory management specialist

**Definition format** (`agents/{id}/AGENT.md`):
```markdown
---
name: Agent Name
description: Brief description for subagent dispatch
llm:                          # Optional: override global settings
  temperature: 0.7
  max_tokens: 4096
allow_skills: true            # Enable skill loading (default: false)
---

System prompt here...
```

LLM settings use deep merge - only specify what you want to override.

### Subagent Dispatch

Agents can delegate to other agents via `subagent_dispatch`:

```
subagent_dispatch(agent_id="cookie", task="Remember this: ...")
```

Each dispatch creates a fresh session that persists to history. Automatically registered when multiple agents exist.

## Skills

On-demand capabilities loaded by the LLM. Unlike tools (always available), skills load only when needed.

**Definition format** (`skills/{id}/SKILL.md`):
```markdown
---
name: Brainstorming
description: Turn ideas into designs through dialogue
---

[Detailed instructions...]
```

**Enable in agent:**
```markdown
---
allow_skills: true
---
```

**Create a skill when:** workflow has multiple steps, needs domain knowledge, benefits from structure.
**Create a tool when:** simple single operation, programmatic action, always available.

## Crons

Scheduled agent invocations.

**Definition format** (`crons/{id}/CRON.md`):
```markdown
---
name: Daily Summary
agent: pickle
schedule: "0 9 * * *"    # 9 AM daily
---

Task description...
```

**Schedule syntax:** `minute hour day month weekday`
- `"*/15 * * * *"` - Every 15 minutes
- `"0 9 * * *"` - Daily at 9 AM
- `"0 */2 * * *"` - Every 2 hours

**Requirements:** Server mode (`picklebot server`), minimum 5-minute granularity, sequential execution.

**Proactive messaging:** Crons can use `post_message` tool to send to configured default platform.

## Memory System

Long-term memories managed by Cookie agent.

**Structure:**
- `topics/` - Timeless facts (preferences, relationships, identity)
- `projects/` - Project state and context
- `daily-notes/` - Day-specific events

**Flows:**
- **Storage:** User shares info → Pickle dispatches to Cookie → Cookie writes to file
- **Retrieval:** User asks → Pickle dispatches → Cookie searches → Returns context

**File format:** Simple markdown with headings.

## Web Tools

### Web Search

Search via `websearch` tool using Brave Search.

```yaml
websearch:
  provider: brave
  api_key: "your-brave-api-key"
```

Get API key at https://brave.com/search/api/

### Web Read

Read web pages via `webread` tool using Crawl4AI.

```yaml
webread:
  provider: crawl4ai
```

No API key needed - uses local browser.

## MessageBus

Chat via Telegram and Discord with shared conversation history.

**Platforms:** Telegram, Discord

**Features:**
- Switch platforms mid-conversation (history carries over)
- User whitelist for access control
- Proactive messaging via `post_message` tool

**Whitelist config:**
```yaml
telegram:
  allowed_chat_ids: ["123456789"]  # Empty = allow all
```

## HTTP API

REST API for programmatic access. Enabled by default in server mode.

```yaml
api:
  host: "127.0.0.1"
  port: 8000
```

**Endpoints:**

| Resource | Endpoints |
|----------|-----------|
| Agents | `GET/POST/PUT/DELETE /agents/{id}` |
| Skills | `GET/POST/PUT/DELETE /skills/{id}` |
| Crons | `GET/POST/PUT/DELETE /crons/{id}` |
| Sessions | `GET/DELETE /sessions/{id}` |
| Memories | `GET/POST/PUT/DELETE /memories/{path}` |
| Config | `GET/PATCH /config` |

**Example:**
```bash
curl http://localhost:8000/agents
curl http://localhost:8000/agents/pickle
```

## Heartbeat

Continuous work pattern using cron jobs. Create a heartbeat cron that checks active projects periodically:

```markdown
---
name: Heartbeat
agent: pickle
schedule: "*/30 * * * *"
---

## Active Tasks
- [ ] Monitor project X
```

Pickle checks project state and takes action autonomously between user interactions.
