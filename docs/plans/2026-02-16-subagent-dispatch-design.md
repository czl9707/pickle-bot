# Subagent Dispatch Tool Design

**Date:** 2026-02-16
**Status:** Approved
**Approach:** Tool Factory Pattern with Dynamic Schema

## Overview

Enable agents to delegate specialized work to other pre-defined agents through a `subagent_dispatch` tool call. Each subagent runs in its own persistent session, and the parent receives the final result plus a session ID for linking.

**Key Design Decisions:**
- Tool name: `subagent_dispatch`
- Tool factory pattern (similar to skill tool)
- Dynamic schema with agent enum (excludes calling agent)
- Separate persistent sessions with parent-child linking via returned session_id
- Task + optional context as string parameters
- Returns JSON with result + session_id
- Unlimited nesting allowed
- Errors raised as tool call failures
- Uses `SilentFrontend` for subagent execution

## Architecture & Components

**New Components:**

1. **`create_subagent_dispatch_tool()` factory** - Located in `src/picklebot/tools/subagent_tool.py`
   - Takes `AgentLoader` and current `agent_id` as parameters
   - Scans available agents, excludes current agent
   - Builds dynamic enum of dispatchable agent IDs
   - Returns configured tool function or `None` if no agents available

2. **Tool Function** - The actual `subagent_dispatch` async function
   - Loads target AgentDef via AgentLoader
   - Creates new Agent instance with SharedContext
   - Creates new AgentSession (persists to history)
   - Runs agent loop with task + context as initial user message
   - Returns `{"result": str, "session_id": str}` as JSON

**Modified Components:**

1. **Agent** (`core/agent.py`) - Add dispatch tool registration in `__init__`
   - Calls `_register_subagent_tool()` method similar to skill tool

2. **AgentDef** (`core/agent_loader.py`) - Add new field
   - `description: str` - Brief description for dispatch tool (required in frontmatter)

**Data Flow:**
```
Parent Agent calls subagent_dispatch(agent_id="reviewer", task="...", context="...")
    ↓
Tool loads AgentDef for "reviewer"
    ↓
Creates new Agent + AgentSession
    ↓
Runs agent loop with task + context using SilentFrontend
    ↓
Returns {"result": "...", "session_id": "uuid-1234"}
    ↓
Parent sees result + session_id in tool response
```

## Tool Factory Implementation

**File:** `src/picklebot/tools/subagent_tool.py`

```python
from picklebot.tools.base import tool
from picklebot.core.agent_loader import AgentLoader
from picklebot.core.context import SharedContext
from picklebot.core.agent import Agent
from picklebot.frontend.base import SilentFrontend
from picklebot.utils.def_loader import DefNotFoundError
import json


def create_subagent_dispatch_tool(
    agent_loader: AgentLoader,
    current_agent_id: str,
    context: SharedContext,
) -> Callable | None:
    """Factory to create subagent dispatch tool with dynamic schema."""

    # Discover available agents, exclude current
    available_agents = agent_loader.discover_agents()
    dispatchable_agents = [a for a in available_agents if a.id != current_agent_id]

    if not dispatchable_agents:
        return None

    # Build description listing available agents
    agents_desc = "<available_agents>\n"
    for agent_def in dispatchable_agents:
        agents_desc += f'  <agent id="{agent_def.id}">{agent_def.description}</agent>\n'
    agents_desc += "</available_agents>"

    # Build enum of dispatchable agent IDs
    dispatchable_ids = [a.id for a in dispatchable_agents]

    @tool(
        name="subagent_dispatch",
        description=f"Dispatch a task to a specialized subagent.\n{agents_desc}",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "enum": dispatchable_ids,
                    "description": "ID of the agent to dispatch to"
                },
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to perform"
                },
                "context": {
                    "type": "string",
                    "description": "Optional context information for the subagent"
                }
            },
            "required": ["agent_id", "task"]
        }
    )
    async def subagent_dispatch(agent_id: str, task: str, context: str = "") -> str:
        """Dispatch task to subagent, return result + session_id."""

        # Load target agent definition
        try:
            target_def = agent_loader.load(agent_id)
        except DefNotFoundError:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Create subagent instance
        subagent = Agent(target_def, context)

        # Build initial message
        user_message = task
        if context:
            user_message = f"{task}\n\nContext:\n{context}"

        # Create new session and run with silent frontend
        session = subagent.new_session()
        response = await session.chat(user_message, SilentFrontend())

        # Return result + session_id as JSON
        result = {
            "result": response,
            "session_id": session.session_id
        }
        return json.dumps(result)

    return subagent_dispatch
```

**Key Points:**
- Dynamic `enum` built from available agents (excludes self)
- `context` has empty string default (optional)
- Injects `AgentLoader` and `SharedContext` for agent creation
- Returns `None` if no dispatchable agents available
- Uses `SilentFrontend` for subagent execution

## Agent Integration

### Agent Constructor

```python
class Agent:
    def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
        self.agent_def = agent_def
        self.context = context
        self.tools = ToolRegistry.with_builtins()
        self.llm = LLMProvider.from_config(agent_def.llm)

        # Add skill tool if allowed
        if agent_def.allow_skills:
            self._register_skill_tool()

        # Add subagent dispatch tool
        self._register_subagent_tool()

    def _register_subagent_tool(self) -> None:
        """Register the subagent dispatch tool if agents are available."""
        subagent_tool = create_subagent_dispatch_tool(
            self.context.agent_loader,
            self.agent_def.id,
            self.context
        )
        if subagent_tool:
            self.tools.register(subagent_tool)
```

**Key Points:**
- Dispatch tool always registered (if agents available), unlike skill tool which is conditional
- Tool is registered once per Agent instance
- Uses factory pattern with current agent ID for self-exclusion

## AgentDef Changes

### Add `description` Field

```python
class AgentDef(BaseModel):
    """Loaded agent definition."""
    id: str
    name: str
    description: str  # Brief description for dispatch tool
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False

    class Config:
        extra = "forbid"
```

### AGENT.md Format

```markdown
---
name: Code Reviewer
description: Reviews code for quality, bugs, and best practices
provider: openai
model: gpt-4
allow_skills: true
---

You are a code reviewer...
```

### Validation Rules

- `description` is required in frontmatter
- Should be concise (1-2 sentences) - used in dispatch tool's agent listing
- AgentLoader will raise `InvalidDefError` if missing

## Error Handling

### Error Cases

1. **Agent not found** - `DefNotFoundError` from `agent_loader.load()`
   - Raise `ValueError(f"Agent '{agent_id}' not found")`
   - Becomes tool call failure, parent agent sees error message

2. **Invalid agent_id in enum** - Shouldn't happen (enum is built from valid agents)
   - If it does, caught by case #1 above

3. **Subagent execution failure** - Exception during `session.chat()`
   - Let it bubble up as tool call failure
   - Session still created and persisted (useful for debugging)

4. **No agents available for dispatch** - Empty `dispatchable_ids` list
   - Return `None` from factory
   - Don't register the tool at all

## Session Linking

Parent and child sessions are linked through the tool return value:

```json
{
  "result": "The code review found 3 issues...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- Parent agent sees session_id in tool result
- Parent can reference or log the session_id
- Child session persisted normally in history
- No additional metadata infrastructure needed

## Implementation Checklist

**Files to create:**
- [ ] `src/picklebot/tools/subagent_tool.py` - `create_subagent_dispatch_tool()` factory

**Files to modify:**
- [ ] `src/picklebot/core/agent_loader.py` - Add `description` field to `AgentDef`
- [ ] `src/picklebot/core/agent.py` - Register dispatch tool in `__init__`

**Implementation steps:**
- [ ] Add `description: str` field to `AgentDef` model
- [ ] Update `AgentLoader` to parse `description` from frontmatter (required)
- [ ] Create `src/picklebot/tools/subagent_tool.py` with factory function
- [ ] Update `Agent.__init__()` to call `_register_subagent_tool()` method
- [ ] Add `_register_subagent_tool()` method to Agent class
- [ ] Import `SilentFrontend` in subagent_tool.py
- [ ] Write unit tests for dispatch tool
- [ ] Update any existing agent definitions with `description` field

**Testing:**
- [ ] Unit test: factory creates tool with correct enum
- [ ] Unit test: factory excludes current agent
- [ ] Unit test: factory returns None when no agents available
- [ ] Integration test: dispatch creates session and returns result + session_id
- [ ] Integration test: dispatch handles agent not found error
- [ ] Integration test: nested dispatch works (subagent dispatches subagent)
