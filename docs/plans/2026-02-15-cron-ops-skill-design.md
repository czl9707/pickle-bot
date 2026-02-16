# Cron Operations Skill Design

**Date:** 2026-02-15
**Status:** Approved

## Overview

A skill that enables full CRUD management of cron jobs through natural conversation. Structured around four commands: `create`, `list`, `update`, `delete`.

The skill will be created at `~/.pickle-bot/skills/cron-ops/SKILL.md`.

## File Structure Reference

```
~/.pickle-bot/crons/
├── inbox-check/
│   └── CRON.md
├── daily-summary/
│   └── CRON.md
```

Each `CRON.md` has YAML frontmatter:

```yaml
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

## Validation Rules

- Required fields: `name`, `agent`, `schedule`
- Schedule must be valid cron syntax
- Minimum 5-minute granularity
- Agent must exist in `~/.pickle-bot/agents/`

## Commands

### `create` - Create a new cron job

1. Gather required info from user request (name, schedule, agent, prompt)
2. If anything missing -> prompt user for it
3. Validate:
   - Schedule syntax (convert natural language if needed)
   - 5-minute granularity
   - Agent exists
4. Create folder and write CRON.md
5. Confirm creation

### `list` - Show all cron jobs

1. Scan `~/.pickle-bot/crons/` directory
2. Display each cron: id, name, schedule (one line per)

### `update` - Modify an existing cron job

1. Identify target cron by id or name
2. Determine what fields to update based on user request
3. Validate changes (schedule syntax, agent exists)
4. Edit CRON.md accordingly
5. Confirm changes

### `delete` - Remove a cron job

1. Identify target cron by id or name
2. Show cron details
3. Ask for confirmation
4. If confirmed -> remove the cron folder
5. Confirm deletion

## Interaction Pattern

The skill instructs the LLM to:

1. **Parse user intent** - Identify which command the user wants
2. **Extract or prompt** - Get required info from request, prompt only if missing
3. **Validate before acting** - Run all validations before modifying files
4. **Report results** - Confirm what was done

## Key Behaviors

- Accept both natural language ("every 30 minutes") and cron syntax ("*/30 * * * *")
- Never prompt for info already provided
- Always confirm before delete
- Show clear error messages for validation failures

## Summary Table

| Operation | Prompts if Missing | Validates | Confirms |
|-----------|-------------------|-----------|----------|
| create | name, schedule, agent, prompt | schedule, granularity, agent | on success |
| list | none | none | no |
| update | fields to change | schedule, agent | on success |
| delete | target cron | cron exists | **always** |

## Constraints

None - full access to all cron operations.
