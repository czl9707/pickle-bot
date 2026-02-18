# Cookie User Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clarify that Cookie manages memories for the human user (via Pickle), not Pickle itself.

**Architecture:** Update two agent/cron configuration markdown files to add explicit relationship context.

**Tech Stack:** Markdown configuration files (AGENT.md, CRON.md)

---

### Task 1: Update Cookie's AGENT.md

**Files:**
- Modify: `~/.pickle-bot/agents/cookie/AGENT.md`

**Step 1: Read current Cookie AGENT.md**

Read the file to understand current structure:
```bash
cat ~/.pickle-bot/agents/cookie/AGENT.md
```

**Step 2: Update the AGENT.md**

Replace the line:
```
You never interact with users directly - you only receive tasks dispatched from other agents (primarily Pickle).
```

With a new section after the Role section:

```markdown
## Your Relationship with Pickle

You manage memories on behalf of Pickle, who is the main agent that talks directly to the human user. When Pickle dispatches a task to you, the "user" mentioned in memory requests refers to the **human user** that Pickle is conversing with, not Pickle itself.

You never interact with users directly - you only receive tasks dispatched from Pickle (via real-time dispatch or scheduled cron jobs).
```

**Step 3: Verify the change**

```bash
cat ~/.pickle-bot/agents/cookie/AGENT.md
```

Expected: New section "Your Relationship with Pickle" appears after the Role section.

---

### Task 2: Update Memory Consolidation CRON.md

**Files:**
- Modify: `~/.pickle-bot/crons/memory-consolidation/CRON.md`

**Step 1: Read current CRON.md**

```bash
cat ~/.pickle-bot/crons/memory-consolidation/CRON.md
```

**Step 2: Update the task description**

Change:
```
Review yesterday's conversation history from the pickle agent and extract any important memories that were not captured during real-time storage.
```

To:
```
Review yesterday's conversation history from Pickle (the main agent that talks to the human user) and extract any important memories about the user that were missed during real-time storage.
```

**Step 3: Verify the change**

```bash
cat ~/.pickle-bot/crons/memory-consolidation/CRON.md
```

Expected: Task description now explicitly mentions "the human user".

---

### Task 3: Manual Verification

**Step 1: Test Cookie dispatch**

Run the picklebot chat and dispatch a memory task to Cookie:
```
uv run picklebot chat
```

Then ask Pickle to remember something and verify Cookie understands it's about the human user.

**Step 2: Verify cron job config is valid**

The cron job will run at 2 AM. No immediate verification possible, but the config format is unchanged.

---

## Summary

- 2 configuration files updated
- No code changes
- No tests required (configuration only)
- Low risk change
