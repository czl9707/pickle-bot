# Design: Cron Prompt Guidelines for post_message

**Date:** 2026-02-20

## Problem

When users create cron jobs via Telegram (e.g., "say hello to me after 5 mins"), the LLM generates a response that goes nowhere. Cron jobs use `SilentFrontend`, so responses disappear in the background. The agent doesn't know to use `post_message` to notify the user.

## Solution

Update the `cron-ops` skill with a **"Cron Prompt Guidelines"** section that teaches Pickle when and how to include `post_message` instructions in cron prompts.

## Changes

**File:** `~/.pickle-bot/skills/cron-ops/SKILL.md`

Add a new section after "Cron Syntax":

```markdown
## Cron Prompt Guidelines

Cron jobs run in the background with no direct output to the user.
The agent executing the cron has no conversation context.

**When the user asks to be notified** (e.g., "tell me", "let me know", "notify me", "say to me", "remind me"):
- Include `post_message` instruction in the prompt
- Specify what content to send

**When the user doesn't ask for notification:**
- No `post_message` needed (e.g., background cleanup, logging, data processing)

**Examples with notification:**
```yaml
---
name: Inbox Summary
agent: pickle
schedule: "0 9 * * *"
---

Check my inbox and use post_message to send me a summary of unread messages.
```

```yaml
---
name: Build Status Check
agent: pickle
schedule: "*/15 * * * *"
---

Check if the CI build is passing. Use post_message to notify me only if it failed.
```

**Examples without notification:**
```yaml
---
name: Log Cleanup
agent: pickle
schedule: "0 0 * * *"
---

Delete log files older than 7 days in the project directory.
```
```

## No Code Changes

This is a skill-only fix. No changes to:
- `CronExecutor`
- `CronDef`
- `post_message_tool`
- Any other code
