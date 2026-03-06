# Slash Commands Redesign

**Date:** 2026-03-06
**Status:** Design Approved

## Overview

Redesign slash commands to be more consistent and add routing management capabilities.

## Changes Summary

| Command | Current | New |
|---------|---------|-----|
| `/agent [id]` | List/switch | List all OR show specific (metadata + content) |
| `/skills [id]` | List all | List all OR show specific (metadata + content) |
| `/crons [id]` | List all | List all OR show specific (metadata + content) |
| `/context` | Show context | No change |
| `/route <pattern> <agent_id>` | — | NEW: Create binding (persist to config) |
| `/bindings` | — | NEW: Show all bindings |

## Modified Commands

### `/agent [id]`

**Behavior:**
- No args: List all agents with `(current)` marker
- With id: Show detailed view

**Detail view includes:**
- Metadata: id, name, description, llm settings
- Full AGENT.md content
- SOUL.md content (if exists)

**Removed:**
- Agent switching functionality (was: `/agent <id>` to switch)

### `/skills [id]`

**Behavior:**
- No args: List all skills
- With id: Show detailed view

**Detail view includes:**
- Metadata: id, name, description
- Full SKILL.md content

### `/crons [id]`

**Behavior:**
- No args: List all crons
- With id: Show detailed view

**Detail view includes:**
- Metadata: id, name, schedule, agent
- Full CRON.md content

## New Commands

### `/route <pattern> <agent_id>`

Creates a routing binding that persists to config.

**Example:**
```
/route platform-telegram:.* pickle
→ ✓ Route bound: `platform-telegram:.*` → `pickle`
```

**Validation:**
- Requires both pattern and agent_id args
- Validates agent exists before creating binding

**Persistence:**
- Writes to `config.user.yaml` under `routing.bindings`
- Uses atomic write (temp file + rename)
- Clears routing table cache after write

### `/bindings`

Lists all current routing bindings.

**Example output:**
```
**Routing Bindings:**
- `platform-telegram:.*` → `pickle`
- `platform-discord:.*` → `cookie`
```

## Implementation Details

### File Changes

**`core/commands/handlers.py`**
- Modify `AgentCommand`: add detail view, remove switch logic
- Modify `SkillsCommand`: add detail view
- Modify `CronsCommand`: add detail view
- Add `RouteCommand`: new class
- Add `BindingsCommand`: new class

**`core/routing.py`**
- Add `persist_binding(pattern, agent_id)`: write to config.user.yaml

**`core/commands/registry.py`**
- Register `RouteCommand` and `BindingsCommand` in `with_builtins()`

**`utils/config.py`**
- May need helper method for persisting bindings (if not already available)

### Persistence Strategy

1. Read existing bindings from `config.user.yaml`
2. Append new binding to the list
3. Write back to file using atomic write
4. Clear routing table cache to force reload

### Error Handling

| Scenario | Response |
|----------|----------|
| `/route` missing args | Usage hint |
| `/route` non-existent agent | "Agent not found" error |
| `/skills <id>` not found | "Skill not found" message |
| `/crons <id>` not found | "Cron not found" message |
| `/agent <id>` not found | "Agent not found" message |

## Design Decisions

### Why remove agent switching?

Routing is now managed via `/route` which provides explicit control over source-to-agent mappings. This separates the concern of "viewing agents" from "configuring routing."

### Why separate `/route` and `/bindings`?

Single responsibility: `/route` is for creating bindings, `/bindings` is for viewing. This keeps commands focused and predictable.

### Why persist to config.user.yaml?

Runtime bindings would be lost on restart. Persisting to config ensures routing changes survive server restarts and provides visibility into the current configuration.
