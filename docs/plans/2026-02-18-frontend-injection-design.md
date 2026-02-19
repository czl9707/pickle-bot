# Frontend Injection for Subagent Visibility

## Overview

Enable visibility into subagent dispatches in messagebus conversations. When Pickle dispatches to Cookie (or other agents), users will see the dispatch and response in their Telegram/Discord chat, making the agent collaboration transparent.

**Example flow:**
```
User: What projects am I working on?
Pickle: @cookie What projects is the user working on?
Cookie: - Found 3 active projects: Pickle-bot development, Documentation update, Code review
Pickle: You're currently working on three projects...
```

## Architecture

**New Frontend Methods** (abstract, all frontends must implement):
```python
show_dispatch_start(calling_agent: str, target_agent: str, task: str)
show_dispatch_result(calling_agent: str, target_agent: str, result: str)
```

**New Frontend Implementation**:
- `MessageBusFrontend` - Posts dispatch messages to messagebus platform
  - Constructor: `MessageBusFrontend(bus: MessageBus, context: Any)`
  - Created fresh per incoming message (lightweight wrapper)
  - Formats messages as simple mentions with 200-char truncation

**Tool Execution Flow Changes**:
- `ToolRegistry.execute_tool(name, frontend, **kwargs)` - Add required frontend parameter
- `BaseTool.execute(frontend, **kwargs)` - Add required frontend parameter
- All tool functions updated to accept `frontend` parameter (even if unused)
- `AgentSession._execute_tool_call()` passes frontend through to registry

## Components

### 1. Frontend Base Class (`frontend/base.py`)

Add new abstract methods:
```python
class Frontend(ABC):
    # ... existing methods ...

    @abstractmethod
    def show_dispatch_start(self, calling_agent: str, target_agent: str, task: str) -> None:
        """Display subagent dispatch start."""

    @abstractmethod
    def show_dispatch_result(self, calling_agent: str, target_agent: str, result: str) -> None:
        """Display subagent dispatch result."""
```

### 2. MessageBusFrontend (new file: `frontend/messagebus_frontend.py`)

Posts dispatch messages to messagebus platform:
```python
class MessageBusFrontend(Frontend):
    def __init__(self, bus: MessageBus, context: Any):
        self.bus = bus
        self.context = context

    def show_dispatch_start(self, calling_agent, target_agent, task):
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        asyncio.create_task(self.bus.reply(msg, self.context))

    def show_dispatch_result(self, calling_agent, target_agent, result):
        truncated = result[:200] + "..." if len(result) > 200 else result
        msg = f"{target_agent}: - {truncated}"
        asyncio.create_task(self.bus.reply(msg, self.context))
```

### 3. ConsoleFrontend Updates (`frontend/console.py`)

Show dispatch events for debugging:
```python
def show_dispatch_start(self, calling_agent, target_agent, task):
    self.console.print(f"[dim]{calling_agent} → @{target_agent}: {task}[/dim]")

def show_dispatch_result(self, calling_agent, target_agent, result):
    truncated = result[:200] + "..." if len(result) > 200 else result
    self.console.print(f"[dim]{target_agent}: {truncated}[/dim]")
```

### 4. SilentFrontend Updates (`frontend/base.py`)

No-op implementations:
```python
def show_dispatch_start(self, calling_agent, target_agent, task):
    pass

def show_dispatch_result(self, calling_agent, target_agent, result):
    pass
```

### 5. Tool System Updates

**ToolRegistry (`tools/registry.py`)**:
```python
async def execute_tool(self, name: str, frontend: "Frontend", **kwargs: Any) -> str:
    tool = self.get(name)
    if tool is None:
        raise ValueError(f"Tool not found: {name}")
    return await tool.execute(frontend, **kwargs)
```

**BaseTool (`tools/base.py`)**:
```python
@abstractmethod
async def execute(self, frontend: "Frontend", **kwargs: Any) -> str:
    """Execute the tool."""
```

**FunctionTool (`tools/base.py`)**:
```python
async def execute(self, frontend: "Frontend", **kwargs: Any) -> str:
    result = self._func(frontend=frontend, **kwargs)
    if asyncio.iscoroutine(result):
        result = await result
    return str(result)
```

**All Builtin Tools (`tools/builtin_tools.py`)**:
Update signatures to accept `frontend` parameter:
```python
async def read_file(path: str, frontend: "Frontend") -> str:
    # ... implementation (doesn't use frontend)
```

### 6. Subagent Tool Updates (`tools/subagent_tool.py`)

Use frontend for visibility:
```python
async def subagent_dispatch(agent_id: str, task: str, context: str = "", frontend: "Frontend" = None) -> str:
    # Get agent names
    calling_agent_name = current_agent_def.name
    target_agent_def = shared_context.agent_loader.load(agent_id)
    target_agent_name = target_agent_def.name

    # Show dispatch start
    frontend.show_dispatch_start(calling_agent_name, target_agent_name, task)

    # Run subagent
    session = subagent.new_session()
    response = await session.chat(user_message, SilentFrontend())

    # Show dispatch result
    frontend.show_dispatch_result(calling_agent_name, target_agent_name, response)

    # Return result
    result = {"result": response, "session_id": session.session_id}
    return json.dumps(result)
```

### 7. MessageBusExecutor Updates (`core/messagebus_executor.py`)

Create MessageBusFrontend per message:
```python
async def _process_messages(self) -> None:
    while True:
        message, platform, context = await self.message_queue.get()

        try:
            # Create frontend with current bus and context
            bus = self.bus_map[platform]
            frontend = MessageBusFrontend(bus, context)

            response = await self.session.chat(message, frontend)
            await bus.reply(content=response, context=context)
        except Exception as e:
            # ... error handling
```

### 8. AgentSession Updates (`core/agent.py`)

Pass frontend through tool execution:
```python
async def _execute_tool_call(
    self,
    tool_call: "LLMToolCall",
    llm_content: str,
    frontend: "Frontend",
) -> str:
    # ... setup ...

    with frontend.show_transient(tool_display):
        try:
            result = await self.agent.tools.execute_tool(tool_call.name, frontend, **args)
        except Exception as e:
            result = f"Error executing tool: {e}"

        return result
```

## Data Flow

### MessageBusExecutor Flow
```
1. Message arrives from Telegram/Discord with context
2. MessageBusExecutor creates: frontend = MessageBusFrontend(bus, context)
3. Calls: session.chat(message, frontend)
4. Frontend is now available throughout the session
```

### Tool Execution Flow
```
AgentSession.chat(message, frontend)
  ↓
AgentSession._handle_tool_calls(tool_calls, frontend)
  ↓
AgentSession._execute_tool_call(tool_call, frontend)
  ↓
ToolRegistry.execute_tool(name, frontend, **args)
  ↓
BaseTool.execute(frontend, **kwargs)
  ↓
Tool function receives frontend parameter
```

### Subagent Dispatch Flow
```
subagent_dispatch tool receives frontend
  ↓
1. frontend.show_dispatch_start("Pickle", "cookie", task)
  ↓ MessageBusFrontend posts to Telegram/Discord
2. Creates subagent session: session.chat(task, SilentFrontend())
  ↓ Subagent runs silently
3. frontend.show_dispatch_result("Pickle", "cookie", result)
  ↓ MessageBusFrontend posts truncated response
4. Returns result to calling agent
```

### Async Posting
MessageBusFrontend uses `asyncio.create_task()` for posting messages to avoid blocking tool execution.

## Error Handling

### MessageBusFrontend Posting Failures
```python
def show_dispatch_start(self, calling_agent, target_agent, task):
    try:
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        asyncio.create_task(self.bus.reply(msg, self.context))
    except Exception as e:
        logger.warning(f"Failed to post dispatch message: {e}")
        # Don't fail the tool execution, just log
```

**Silent degradation**: If posting fails, log warning but continue execution. Users will still get the final response.

### Subagent Execution Errors
- Subagent errors are caught by the subagent tool (existing behavior)
- Error message is returned as result
- `show_dispatch_result()` shows the error message (truncated)

### Frontend is None Scenarios
- Should never happen with required parameter approach
- If somehow passed, tool execution will fail early with clear error

## Testing

### Unit Tests

1. **MessageBusFrontend Tests**
   - Test error handling when bus.reply() fails (continues execution, logs warning)

2. **Tool Registry Tests**
   - Test execute_tool passes frontend correctly
   - Test all builtin tools work with frontend parameter

3. **Subagent Tool Tests**
   - Test frontend.show_dispatch_start() called before dispatch
   - Test frontend.show_dispatch_result() called with result
   - Test with MessageBusFrontend mock

## Implementation Notes

- Frontend parameter is required in all tool signatures (no optional parameters)
- All builtin tools (read, write, edit, bash) will accept but ignore frontend parameter
- MessageBusFrontend is lightweight and created fresh per message
- Async posting ensures tool execution isn't blocked by message posting
