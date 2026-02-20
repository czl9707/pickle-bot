# Cron Operations Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a skill that enables full CRUD management of cron jobs through natural conversation.

**Architecture:** A single SKILL.md file with YAML frontmatter and instructional content. Uses the existing skill system (SkillLoader, skill_tool) which loads skills from `~/.pickle-bot/skills/`. No code changes required.

**Tech Stack:** Markdown, YAML frontmatter

---

## Task 1: Create the skill directory

**Files:**
- Create: `~/.pickle-bot/skills/cron-ops/SKILL.md`

**Step 1: Create directory structure**

```bash
mkdir -p ~/.pickle-bot/skills/cron-ops
```

**Step 2: Verify directory exists**

```bash
ls -la ~/.pickle-bot/skills/
```

Expected: Directory listing shows `cron-ops`

---

## Task 2: Write the SKILL.md file

**Files:**
- Create: `~/.pickle-bot/skills/cron-ops/SKILL.md`

**Step 1: Create SKILL.md with frontmatter and content**

```markdown
---
name: Cron Operations
description: Manage cron jobs - create, list, update, and delete scheduled tasks
---

# Cron Operations

Manage cron jobs in the pickle-bot system.

## Cron File Structure

Crons live in `~/.pickle-bot/crons/[cron-id]/CRON.md`:

```
~/.pickle-bot/crons/
├── inbox-check/
│   └── CRON.md
├── daily-summary/
│   └── CRON.md
```

Format:

```yaml
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

## Validation Rules

- **Required fields:** `name`, `agent`, `schedule`, and prompt body
- **Schedule:** Must be valid cron syntax (5 fields)
- **Granularity:** Minimum 5 minutes between runs
- **Agent:** Must exist in `~/.pickle-bot/agents/`

## Commands

### create

Create a new cron job.

1. Extract from request: `name`, `schedule`, `agent`, `prompt`
2. If missing → prompt user for specific field only
3. Convert natural language schedule to cron (e.g., "every 30 minutes" → `*/30 * * * *`)
4. Validate schedule syntax and 5-minute granularity
5. Verify agent exists: check `~/.pickle-bot/agents/[agent]/AGENT.md`
6. Generate cron-id from name (lowercase, dashes for spaces)
7. Create folder: `~/.pickle-bot/crons/[cron-id]/`
8. Write CRON.md with frontmatter and prompt
9. Confirm: "Created cron '[name]' running [schedule] with agent [agent]"

### list

List all cron jobs.

1. Read directories in `~/.pickle-bot/crons/`
2. For each, parse CRON.md frontmatter
3. Display one line per cron: `[cron-id] | [name] | [schedule]`
4. If no crons: "No cron jobs configured"

### update

Modify an existing cron job.

1. Identify target by cron-id or name
2. Parse user request to determine which fields to change
3. If changing schedule → validate syntax and granularity
4. If changing agent → verify it exists
5. Edit CRON.md, updating only specified fields
6. Confirm: "Updated [cron-id]: changed [fields]"

### delete

Remove a cron job.

1. Identify target by cron-id or name
2. Read and display: `[cron-id]: [name] - [schedule]`
3. Ask: "Delete this cron job? (yes/no)"
4. If yes → `rm -rf ~/.pickle-bot/crons/[cron-id]`
5. Confirm: "Deleted cron '[name]'"

## Natural Language Schedule Examples

- "every 5 minutes" → `*/5 * * * *`
- "every 30 minutes" → `*/30 * * * *`
- "hourly" → `0 * * * *`
- "daily at 9am" → `0 9 * * *`
- "every monday at 8am" → `0 8 * * 1`
- "weekdays at noon" → `0 12 * * 1-5`

## Cron Syntax Reference

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

Special characters:
- `*` - any value
- `*/n` - every n units
- `,` - value list separator
- `-` - range
```

**Step 2: Verify file content**

```bash
head -20 ~/.pickle-bot/skills/cron-ops/SKILL.md
```

Expected: Shows frontmatter and beginning of skill content

---

## Task 3: Test skill discovery

**Step 1: Verify skill is discoverable**

Start a chat session and check if the skill appears in available skills:

```bash
cd /home/zain_chen/kiyo-n-zane/pickle-bot
uv run picklebot chat
```

Then use the skill tool to see available skills, or check the skill tool description lists "Cron Operations".

Expected: Skill "cron-ops" appears in available skills

**Step 2: Test loading the skill**

In the chat session, request to load the cron-ops skill.

Expected: Skill content loads and you can perform cron operations

---

## Task 4: Commit documentation

**Files:**
- Modify: `docs/plans/2026-02-15-cron-ops-skill-design.md` (already committed)

**Step 1: Verify all changes are committed**

```bash
git status
```

Expected: Clean working tree (skill file is in user config, not repo)

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create skill directory | `~/.pickle-bot/skills/cron-ops/` |
| 2 | Write SKILL.md | `~/.pickle-bot/skills/cron-ops/SKILL.md` |
| 3 | Test skill discovery | Manual testing |
| 4 | Commit documentation | Already done |
