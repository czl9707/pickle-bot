# Cron Post Message Guidelines Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update cron-ops skill with guidelines for using post_message in cron prompts.

**Architecture:** Documentation-only change. Add a "Cron Prompt Guidelines" section to the skill file that teaches Pickle when to include post_message instructions (when user asks to be notified) vs when not to (background tasks).

**Tech Stack:** Markdown skill file

---

### Task 1: Add Cron Prompt Guidelines section

**Files:**
- Modify: `~/.pickle-bot/skills/cron-ops/SKILL.md` (append after Cron Syntax section)

**Step 1: Add the new section**

Edit `~/.pickle-bot/skills/cron-ops/SKILL.md` and append after the "Cron Syntax" section:

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

**Step 2: Verify the skill file is valid markdown**

Read the file and confirm the new section appears correctly after Cron Syntax.

**Step 3: Commit**

```bash
git add docs/plans/2026-02-20-cron-post-message-guidelines.md
git commit -m "docs: add implementation plan for cron post_message guidelines"
```

---

### Task 2: Manual Verification

**Step 1: Test with Pickle**

In a new conversation with Pickle, ask: "Say hello to me in 5 minutes"

**Step 2: Verify the created cron**

Check that the cron prompt includes `post_message` instruction, e.g.:

```yaml
---
name: Hello Reminder
agent: pickle
schedule: "* * * * *"  # appropriate 5-min schedule
one_off: true
---

Use post_message to say hello to the user.
```

**Step 3: Final commit (if any fixes needed)**

```bash
git add ~/.pickle-bot/skills/cron-ops/SKILL.md
git commit -m "docs(skill): add cron prompt guidelines for post_message usage"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add Cron Prompt Guidelines section | `~/.pickle-bot/skills/cron-ops/SKILL.md` |
| 2 | Manual verification | Test with Pickle |
