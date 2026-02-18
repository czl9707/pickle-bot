# Cookie User Context Design

## Problem

Cookie, the memory management agent, currently considers Pickle as its user instead of the actual human user. This causes confusion when Cookie stores memories - references to "the user" are ambiguous.

## Root Cause

Cookie's AGENT.md system prompt doesn't clarify the relationship between Cookie, Pickle, and the human user. Cookie receives tasks from:
1. Real-time dispatch from Pickle (when user says something worth remembering)
2. Scheduled cron jobs (daily memory consolidation)

In both cases, Cookie has no context that the "user" in memory requests refers to the human, not Pickle.

## Solution

Update two configuration files to clarify the relationship:

### 1. Cookie's AGENT.md (`~/.pickle-bot/agents/cookie/AGENT.md`)

Add a section clarifying the relationship with Pickle:

```markdown
## Your Relationship with Pickle

You manage memories on behalf of Pickle, who is the main agent that talks directly to the human user. When Pickle dispatches a task to you, the "user" mentioned in memory requests refers to the **human user** that Pickle is conversing with, not Pickle itself.

You never interact with users directly - you only receive tasks dispatched from Pickle (via real-time dispatch or scheduled cron jobs).
```

### 2. Memory Consolidation CRON.md (`~/.pickle-bot/crons/memory-consolidation/CRON.md`)

Update the task description to be explicit:

```markdown
---
name: Memory Consolidation
agent: cookie
schedule: "0 2 * * *"
---

Review yesterday's conversation history from Pickle (the main agent that talks to the human user) and extract any important memories about the user that were missed during real-time storage.

Focus on:
- User preferences mentioned in passing
- Project decisions or insights
- Important context that might be useful in future sessions

Do not duplicate memories that already exist in the memory store.
```

## Impact

- No code changes required
- Cookie will correctly attribute memories to the human user
- Memory consolidation cron job will have clearer context
