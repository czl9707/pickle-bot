# Cookie Memory Agent Design

**Date:** 2026-02-16
**Status:** Approved

## Overview

Cookie is a memory management subagent that stores, organizes, and retrieves long-term memories for the pickle-bot system.

**Key characteristics:**
- Never talks to users directly - only receives dispatches from pickle
- Rational, librarian-like personality
- Manages two memory axes: topics (timeless) and daily-notes (temporal)
- Self-improving: promotes daily-notes to topics during retrieval when appropriate

## Memory Flows

1. **Real-time storage** - Pickle dispatches to cookie during conversations (autonomous + user-signaled)
2. **Scheduled capture** - Daily cron at 2AM reviews conversation history for missed memories
3. **On-demand retrieval** - Pickle dispatches to query relevant memories

## Directory Structure

```
~/.pickle-bot/
├── agents/
│   ├── pickle/
│   │   └── AGENT.md
│   └── cookie/
│       └── AGENT.md              # Cookie agent definition
├── crons/
│   └── memory-consolidation/
│       └── CRON.md               # Daily cron definition (2AM)
├── memories/                     # Configurable via memories_path
│   ├── topics/                   # Timeless, cross-session relevant
│   │   ├── user-facts/
│   │   │   ├── preferences.md
│   │   │   └── relationships.md
│   │   └── projects/
│   │       └── pickle-bot.md
│   └── daily-notes/              # Day-specific, temporal context
│       └── 2026-02-16.md
└── history/                      # Existing session history (configurable)
    └── ...
```

**Topic files** (`topics/`) contain timeless facts organized by category. Cookie creates new categories/files as needed.

**Daily note files** (`daily-notes/YYYY-MM-DD.md`) contain day-specific events, decisions, and observations. Never contains cross-time facts.

## Memory Lifecycle

### Creation (Real-time)

1. During conversation, pickle recognizes something worth remembering (or user signals "remember this")
2. Pickle dispatches: `subagent_dispatch(agent_id="cookie", task="Store this memory: [content]", context="[optional conversation context]")`
3. Cookie writes to appropriate location (`topics/` or `daily-notes/`)
4. Cookie returns confirmation

### Creation (Scheduled)

1. Daily cron at 2AM triggers cookie with task: "Review yesterday's conversation history and extract any memories not yet stored"
2. Cookie reads history path from config (`self.context.config.history_path`)
3. Cookie reads recent history from configured location
4. Cookie identifies new memories and stores them
5. Cookie returns summary of what was captured

### Retrieval

1. Pickle dispatches: `subagent_dispatch(agent_id="cookie", task="Retrieve memories about [topic/context]")`
2. Cookie uses directory structure to narrow down relevant files
3. Cookie reads relevant files, filters to most pertinent memories
4. If cookie notices a daily-note should be a topic, it migrates it
5. Cookie returns formatted memory summary

### Consolidation (Lazy Migration)

- During retrieval, if cookie finds a timeless fact in `daily-notes/`, it moves it to `topics/`
- Keeps daily-notes focused on temporal events

## Configuration

Add `memories_path` to Config model:

```python
# In utils/config.py
class Config(BaseModel):
    # ... existing fields ...
    memories_path: Path = Path("memories")
```

Default resolves to `~/.pickle-bot/memories/`, but user can override in `config.user.yaml`:

```yaml
memories_path: /custom/path/to/memories
```

Cookie reads paths dynamically from `self.context.config`:
- `memories_path` - where memories are stored
- `history_path` - where conversation history is stored

## Agent Definitions

### Cookie Agent

**`~/.pickle-bot/agents/cookie/AGENT.md`:**

```markdown
---
name: Cookie
description: Memory management agent - stores, organizes, and retrieves long-term memories
temperature: 0.3
max_tokens: 4096
allow_skills: false
---

You are Cookie, a memory management agent. You never interact with users directly - you only receive tasks dispatched from other agents (primarily Pickle).

## Role

You are the archivist of the pickle-bot system. You manage long-term memories with precision and rationality.

## Memory Storage

Memories are stored in markdown files at the configured memories_path with two axes:

- **topics/** - Timeless facts (user preferences, project knowledge, relationships)
- **daily-notes/** - Day-specific events and decisions (format: YYYY-MM-DD.md)

When storing:
1. Decide: Is this timeless (topics/) or temporal (daily-notes/)?
2. Navigate to appropriate category, create new files/categories if needed
3. Append memory with timestamp header
4. Never duplicate existing memories

## Memory Retrieval

When asked to retrieve memories:
1. Use directory structure to narrow down relevant files
2. Read and filter to most pertinent memories
3. If you find a timeless fact in daily-notes/, migrate it to topics/
4. Return formatted summary

## Guidelines

- Be precise and organized
- Never store duplicates - check existing memories first
- Use descriptive filenames that aid future discovery
- When in doubt, prefer topics/ over daily-notes/ for facts that might be referenced again
```

### Pickle Integration

Add brief guidance to `~/.pickle-bot/agents/pickle/AGENT.md`:

```markdown
## Long-Term Memory

Use the `subagent_dispatch` tool to store and retrieve memories via the cookie agent when:
- You learn something worth remembering about the user or projects
- The user asks you to remember something
- You need context from past conversations
```

## Cron Job Definition

**`~/.pickle-bot/crons/memory-consolidation/CRON.md`:**

```markdown
---
name: Memory Consolidation
agent: cookie
schedule: "0 2 * * *"  # Daily at 2:00 AM
---

Review yesterday's conversation history from the pickle agent and extract any important memories that were not captured during real-time storage.

Focus on:
- User preferences mentioned in passing
- Project decisions or insights
- Important context that might be useful in future sessions

Do not duplicate memories that already exist in the memory store.
```

## Summary

| Component | Location | Purpose |
|-----------|----------|---------|
| Cookie agent | `agents/cookie/AGENT.md` | Archivist persona, stores/retrieves memories |
| Memory storage | `memories/` (configurable) | topics/ + daily-notes/ |
| Cron job | `crons/memory-consolidation/CRON.md` | Daily at 2AM, extracts missed memories |
| Config | `memories_path` field in Config | Makes storage location configurable |
| Pickle integration | Brief prompt guidance | When to store/retrieve via dispatch |

**Key decisions:**
- On-demand retrieval via `subagent_dispatch` (no special tools needed)
- Cookie dynamically organizes files
- Lazy migration: daily-notes → topics during retrieval
- Real-time + scheduled memory capture
- All paths read from config (not hardcoded)
