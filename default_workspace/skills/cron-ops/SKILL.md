---
name: Cron Ops
description: Create, list, and delete scheduled cron jobs
tools:
  - read
  - write
  - bash
---

Help users manage scheduled cron jobs in pickle-bot.

## What is a Cron?

A cron is a scheduled task that runs at specified intervals. Crons are stored as `CRON.md` files at `{{crons_path}}/<name>/CRON.md`.

**Important:** Crons run without user present. There's no direct interaction. Use `post_message` tool to deliver results or notifications to the user.

## Schedule Syntax

Standard cron format: `minute hour day month weekday`

Examples:
- `0 9 * * *` - Every day at 9:00 AM
- `*/30 * * * *` - Every 30 minutes
- `0 0 * * 0` - Every Sunday at midnight
- `0 */2 * * *` - Every 2 hours

## Operations

### Create a Cron

1. Ask what task should run and when
2. Determine the schedule
3. Ask which agent should run the task
4. Create the directory and CRON.md file

### List Crons

Use `bash` to list directories:
```bash
ls {{crons_path}}
```

### Delete a Cron

1. List available crons
2. Confirm which one to delete
3. Use `bash` to remove:
```bash
rm -rf {{crons_path}}/<cron-name>
```

## Cron Template

```markdown
---
name: Cron Name
agent: pickle
schedule: "0 9 * * *"
---

Task description for the agent to execute.

Remember to use post_message to notify the user of results.
```
