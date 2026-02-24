---
name: cron-ops
description: Create, list, and delete scheduled cron jobs
---

Help users manage scheduled cron jobs in pickle-bot.

## What is a Cron?

A cron is a scheduled task that runs at specified intervals. Crons are stored as `CRON.md` files at `{{crons_path}}/<name>/CRON.md`.

## Schedule Syntax

Standard cron format: `minute hour day month weekday`

Examples:
- `0 9 * * *` - Every day at 9:00 AM
- `*/30 * * * *` - Every 30 minutes
- `0 0 * * 0` - Every Sunday at midnight

## Operations

### Create

1. Ask what task should run and when
2. Determine the schedule
3. Ask which agent should run the task
4. Create the directory and CRON.md file

### List

Use `bash` to list directories:
```bash
ls {{crons_path}}
```

### Delete

1. List available crons
2. Confirm which one to delete
3. Use `bash` to remove:
```bash
rm -rf {{crons_path}}/<cron-name>
```

## Cron Prompt Guidelines

Cron jobs run in the background with no direct output to the user. The agent executing the cron has no conversation context.

**When the user asks to be notified** (e.g., "tell me", "let me know", "remind me"):
- Include `post_message` instruction in the prompt

**When the user doesn't ask for notification:**
- No `post_message` needed (e.g., background cleanup, data processing)

## Cron Template

```markdown
---
name: Cron Name
agent: pickle
schedule: "0 9 * * *"
---

Task description for the agent to execute.
```

**With notification:**
```markdown
---
name: Daily Summary
agent: pickle
schedule: "0 9 * * *"
---

Check my inbox and use post_message to send me a summary.
```
