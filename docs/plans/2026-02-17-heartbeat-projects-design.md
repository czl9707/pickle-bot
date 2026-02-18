# Heartbeat & Projects Memory Design

## Overview

Enable pickle-bot to work continuously on projects by:
1. Adding a periodic "heartbeat" cron that checks for work
2. Separating project memories from user memories
3. Updating Cookie agent to manage project state

## Problem

Currently:
- No periodic check-in mechanism for active projects
- Projects are mixed with user facts in `topics/`
- No clear way to track project state (active, blocked, next steps)

## Solution

### 1. Heartbeat Cron

Create `~/.pickle-bot/crons/heartbeat/CRON.md`:

```markdown
---
name: Heartbeat
agent: pickle
schedule: "*/30 * * * *"
---

## Active Tasks

<!-- Agent adds periodic tasks here as checklist items -->

## Completed

<!-- Move completed tasks here -->
```

**Behavior:**
- Runs every 30 minutes
- Agent reads tasks from body, executes them
- If no tasks, does nothing
- Users tell agent to add/remove tasks: "Check on project X periodically"

### 2. Projects Memory Axis

New memory structure:

```
memories/
├── topics/           # User facts (timeless)
│   ├── identity.md
│   └── preferences.md
├── projects/         # Project state (dynamic)  <-- NEW
│   ├── project-name.md
│   └── ...
└── daily-notes/      # Events (temporal)
    └── 2026-02-17.md
```

**Project memory format:**

```markdown
# Project Name

## Status
active | blocked | paused | done

## Context
- Key facts about the project
- Technologies, team, constraints

## Progress
- Recent work completed
- Current state

## Next Steps
- [ ] Task 1
- [ ] Task 2

## Blockers
- Any blocking issues
```

### 3. Cookie Agent Update

Update `~/.pickle-bot/agents/cookie/AGENT.md` to include projects axis:

```markdown
## Memory Storage

Memories are stored in markdown files with three axes:

- **topics/** - Timeless facts about the user (preferences, identity)
- **projects/** - Project state (status, progress, next steps, blockers)
- **daily-notes/** - Day-specific events and decisions

When storing project information:
1. Create/update file at `projects/{project-name}.md`
2. Track status, progress, next steps, and blockers
3. Keep status updated as work progresses
```

## Files to Change

| File | Action |
|------|--------|
| `~/.pickle-bot/crons/heartbeat/CRON.md` | Create |
| `~/.pickle-bot/agents/cookie/AGENT.md` | Update |
| `src/picklebot/core/agent.py` or similar | Document projects axis (optional) |

## User Workflow

1. **Assign project**: "I'm working on project X, it's a React app..."
2. **Cookie stores**: Creates `projects/project-x.md` with context
3. **Add to heartbeat**: "Check on project X periodically"
4. **Heartbeat fires**: Agent reads project state, acts if needed
5. **Update state**: Cookie updates project status as work progresses

## Success Criteria

- [x] Heartbeat cron runs every 30 minutes
- [x] Projects stored separately from user facts
- [x] Cookie can manage project memories
- [x] Heartbeat can read project state and act

## Implementation

**Completed 2026-02-17:**

1. Created `~/.pickle-bot/crons/heartbeat/CRON.md` with 30-minute schedule
2. Added `projects/` axis to memory system (convention)
3. Updated Cookie's `AGENT.md` with project memory format and guidelines
4. Updated `CLAUDE.md` to document heartbeat and projects
