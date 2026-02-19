# Session-Scoped Tool Registration Design

**Date**: 2026-02-18
**Status**: Approved

## Problem

The `post_message` tool is currently available whenever messagebus is configured, regardless of execution context. This creates confusion when an agent is chatting directly with a user (CLI or MessageBus) - the tool's purpose is proactive messaging, but the user is already in the conversation.

## Goal

Make `post_message` available only in non-interactive contexts (where there's no live user waiting), specifically `SessionMode.JOB` contexts like cron jobs.

## Solution

Move tool registration from `Agent.__init__()` to `new_session()`. Each `AgentSession` owns its own `ToolRegistry` with tools appropriate for its session mode.

## Tool Categories

| Category | Tools | Availability |
|----------|-------|--------------|
| **Base** | read, write, edit, glob, grep, bash | All sessions |
| **Mode-optional** | post_message | JOB mode only |
| **Config-optional** | skill, subagent_dispatch | All sessions (if configured) |

## Architecture Changes

### AgentSession

Add `tools` and `mode` fields:

```python
class AgentSession:
    def __init__(self, tools: ToolRegistry, mode: SessionMode, ...):
        self.tools = tools  # NEW: session owns its tools
        self.mode = mode    # NEW: store session mode
        # ... existing history management
```

### Agent

Remove persistent tool registry, become a factory:

```python
class Agent:
    def __init__(self, agent_def, context):
        self.agent_def = agent_def
        self.context = context
        # No longer stores ToolRegistry

    def new_session(self, mode: SessionMode) -> AgentSession:
        tools = self._build_tools(mode)  # Build fresh registry
        return AgentSession(tools=tools, mode=mode, ...)

    def _build_tools(self, mode: SessionMode) -> ToolRegistry:
        registry = ToolRegistry()
        self._register_base_tools(registry)
        self._register_config_optional_tools(registry)
        if mode == SessionMode.JOB:
            self._register_post_message_tool(registry)
        return registry
```

## Data Flow

```
Agent.new_session(SessionMode.JOB)
    │
    ├─→ _build_tools(JOB)
    │       ├─→ Register base tools (read, write, etc.)
    │       ├─→ Register skill (if skills exist)
    │       ├─→ Register subagent_dispatch (if other agents exist)
    │       └─→ Register post_message (because JOB mode) ✓
    │
    └─→ AgentSession(tools=registry, mode=JOB)
```

## Files Affected

| File | Changes |
|------|---------|
| `src/picklebot/core/agent.py` | Remove `self.tools`, add `_build_tools()`, update `new_session()` |
| `src/picklebot/core/session.py` | Add `tools: ToolRegistry` field, add `mode: SessionMode` field |
| `src/picklebot/tools/subagent_tool.py` | Update to use `session.tools` instead of `agent.tools` |

## Implementation Details

### AgentSession changes (`session.py`)

- Add `tools` and `mode` as constructor params
- Store them as instance attributes
- No changes to history management

### Agent changes (`agent.py`)

- Remove `self.tools` and `_register_*_tool()` methods
- Add `_build_tools(mode: SessionMode) -> ToolRegistry`
- `_build_tools()` creates fresh registry and registers tools inline
- `new_session()` calls `_build_tools()` and passes registry to session
- Update `chat()` method to use `session.tools` for schema generation

### Subagent tool changes (`subagent_tool.py`)

- Currently accesses `self.agent.tools` for its own tool registration
- Change to create its own tool registry or pass through context

## Error Handling

No new error cases introduced. Existing error paths remain:

- **Tool not found**: If a tool factory returns `None`, it's simply not registered
- **Invalid mode**: `SessionMode` is an enum, caught at type-check time

Code accessing `agent.tools` directly will fail - this is intentional (tools are session-scoped now).

## Testing Considerations

| Scenario | Verification |
|----------|--------------|
| CLI chat | `post_message` tool NOT in schema |
| MessageBus chat | `post_message` tool NOT in schema |
| Cron job | `post_message` tool IS in schema |
| Subagent dispatch | `post_message` tool IS in schema (uses JOB mode) |
| Skills exist | `skill` tool registered in all modes |
| No skills | `skill` tool not registered |
| Multiple sessions | Each session has independent tool registry |

## Scope

3 files changed, ~50-80 lines touched.
