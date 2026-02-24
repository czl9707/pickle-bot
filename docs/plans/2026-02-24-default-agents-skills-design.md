# Default Agents & Skills Design

Design for the initial minimal set of agents and skills that ship with pickle-bot.

## Overview

This design defines the default agents and skills for pickle-bot's initial release. Users can customize these later based on their needs.

**Scope:**
- 2 Agents: Pickle (main assistant), Cookie (memory manager)
- 2 Skills: cron-ops, skill-creator

**Constraints:**
- Each file under 100 lines
- Minimal but complete
- Template variables for runtime paths

---

## Agents

### Pickle

**Purpose:** General-purpose assistant with cat personality for daily tasks and coding.

**Frontmatter:**
```yaml
name: Pickle
description: A friendly cat assistant for daily tasks and coding
allow_skills: true
llm:
  temperature: 0.7
```

**Key sections:**
1. **Identity** - Gentle cat, warm and helpful, subtle cat mannerisms (not overly cute)
2. **Role** - Primary assistant for user interaction, handles general tasks and coding
3. **Memory** - Delegate memory operations to Cookie via `subagent_dispatch`
4. **Workspace Context** - Template variables (`{{workspace}}`, `{{skills_path}}`, etc.)
5. **Behavior** - Honest about unknowns, graceful corrections

**Design decisions:**
- Cat personality is subtle, not cutesy - focuses on being genuinely helpful
- Temperature 0.7 for conversational flexibility
- `allow_skills: true` for extensibility

---

### Cookie

**Purpose:** Memory management specialist that manages memories on behalf of Pickle for the user.

**Frontmatter:**
```yaml
name: Cookie
description: Memory manager for storing, organizing, and retrieving memories
llm:
  temperature: 0.3
```

**Key sections:**
1. **Identity** - Focused, efficient, precise with data
2. **Role** - Manages memories on behalf of Pickle for the user (not direct user interaction)
3. **Memory Structure** - Three axes at `{{memories_path}}`:
   - `topics/` - Timeless facts (preferences, identity)
   - `projects/` - Project-specific context and decisions
   - `daily-notes/` - Day-specific events and notes
4. **Operations** - Store, retrieve, search, organize, consolidate
5. **Smart Hybrid Behavior** - Make reasonable decisions by default, ask for confirmation on ambiguous cases
6. **Tools** - `read`, `write`, `edit`, `bash` for file operations

**Design decisions:**
- Temperature 0.3 for precision and consistency
- "On behalf of Pickle" clarifies the delegation relationship
- Smart hybrid: autonomous for clear cases, asks user for ambiguous ones

---

## Skills

### cron-ops

**Purpose:** Create, list, and delete scheduled cron jobs.

**Frontmatter:**
```yaml
name: Cron Ops
description: Create, list, and delete scheduled cron jobs
tools:
  - read
  - write
  - bash
```

**Key sections:**
1. **What is a Cron** - Scheduled agent invocation, stored as CRON.md files
2. **Hidden Execution** - Crons run without user present, no direct interaction
3. **post_message for Crons** - Use `post_message` tool to deliver results/notifications to user
4. **Schedule Syntax** - Standard cron format: `minute hour day month weekday`
5. **Operations**:
   - Create: Ask task + schedule, write to `{{crons_path}}/<name>/CRON.md`
   - List: Use `bash` to list directories
   - Delete: Confirm with user, remove directory
6. **Cron Template** - Example CRON.md structure

**Design decisions:**
- Emphasize `post_message` usage since crons are hidden
- Fix tool names from `read_file` to `read` (match actual tools)
- Include delete operation (was missing)

---

### skill-creator

**Purpose:** Search, install, verify, and create skills for pickle-bot.

**Frontmatter:**
```yaml
name: Skill Creator
description: Search, install, verify, and create skills for pickle-bot
tools:
  - read
  - write
  - bash
```

**Key sections:**
1. **What is a Skill** - Reusable prompt with YAML frontmatter
2. **Workflow**:
   - **Search**: Use `npx skills` or `npx clawhub` to find existing skills
   - **Install**: Install if suitable for the use case
   - **Verify**: Check validity and safety after installation
   - **Create**: If nothing fits, create from scratch
3. **Verification Checklist**:
   - Valid frontmatter (name, description)
   - Valid tool names
   - No dangerous patterns (arbitrary code execution, file deletion outside workspace)
4. **Skill Template** - Example SKILL.md structure

**Design decisions:**
- Combined installer + creator into one skill
- npm-based skill discovery (`npx skills`, `npx clawhub`)
- Safety verification after installation
- Fix tool names from `write_file` to `write`

---

## Template Variables

All agents and skills should use these runtime variables:

| Variable | Description |
|----------|-------------|
| `{{workspace}}` | Root workspace directory |
| `{{agents_path}}` | Path to agents directory |
| `{{skills_path}}` | Path to skills directory |
| `{{crons_path}}` | Path to crons directory |
| `{{memories_path}}` | Path to memories directory |
| `{{history_path}}` | Path to session history |

---

## Estimated File Sizes

| File | Estimated Lines |
|------|-----------------|
| Pickle AGENT.md | ~50-60 |
| Cookie AGENT.md | ~60-70 |
| cron-ops SKILL.md | ~70-80 |
| skill-creator SKILL.md | ~70-80 |
| **Total** | ~250-290 |

All files stay under 100 lines as required.
