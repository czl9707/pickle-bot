# Async Frontend Design

## Overview

Enhance the Frontend abstraction so all message responses flow through frontend objects instead of bypassing to native platform APIs. This unifies the output path and prepares MessageBus for future queue-based architecture.

## Goals

- All output routes through Frontend abstraction
- Errors isolated - never block main loop
- Consistent async interface across all frontends
- Agent responses include agent context for display

## Interface Changes

### Frontend Base Class

All methods become async:

```python
class Frontend(ABC):
    @abstractmethod
    async def show_welcome(self) -> None:
        """Display welcome message."""

    @abstractmethod
    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        """Display a message with optional agent context."""

    @abstractmethod
    async def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""

    @abstractmethod
    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield

    @abstractmethod
    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Display subagent dispatch notification."""
        yield
```

### Parameter Semantics

- `show_message(content, agent_id=None)`:
  - `agent_id` provided → prefix with agent name (agent response)
  - `agent_id` is None → show content as-is (raw output)
- `show_dispatch()` → context manager for dispatch lifecycle
  - Shows "start" notification on enter
  - Result handled separately via `show_message()` with subagent's `agent_id`

## Implementations

### MessageBusFrontend

All methods call `bus.reply()` with try/catch for error isolation:

```python
class MessageBusFrontend(Frontend):
    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        if agent_id:
            content = f"[{agent_id}]: {content}"
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")

    async def show_system_message(self, content: str) -> None:
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send system message: {e}")

    async def show_welcome(self) -> None:
        pass  # No welcome on incoming messages

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        yield  # No transient display on messagebus

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        try:
            await self.bus.reply(msg, self.context)
        except Exception as e:
            logger.warning(f"Failed to send dispatch notification: {e}")
        yield
```

### ConsoleFrontend

Async wrappers around sync Rich operations:

```python
class ConsoleFrontend(Frontend):
    async def show_welcome(self) -> None:
        self.console.print(Panel(...))
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        if agent_id:
            self.console.print(f"[bold cyan]{agent_id}:[/bold cyan] {content}")
        else:
            self.console.print(content)

    async def show_system_message(self, content: str) -> None:
        self.console.print(content)

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        self.console.print(f"[dim]{calling_agent} → @{target_agent}: {task}[/dim]")
        yield
```

### SilentFrontend

Async no-ops for unattended execution:

```python
class SilentFrontend(Frontend):
    async def show_welcome(self) -> None:
        pass

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        pass

    async def show_system_message(self, content: str) -> None:
        pass

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        yield
```

## Caller Changes

### AgentSession.chat()

Call `show_message()` at end instead of just returning:

```python
async def chat(self, message: str, frontend: "Frontend") -> str:
    # ... existing logic ...

    # Show response via frontend
    await frontend.show_message(content, agent_id=self.agent_id)
    return content  # Still return for history/other purposes
```

### ChatLoop (cli/chat.py)

Remove manual response display:

```python
# Before
response = await session.chat(user_input, self.frontend)
self.frontend.show_message(f"[bold cyan]{self.agent_def.name}:[/bold cyan] {response}")

# After
response = await session.chat(user_input, self.frontend)
# session.chat() handles showing the response
```

### MessageBusExecutor

Remove direct `bus.reply()` call:

```python
# Before
response = await self.session.chat(message, frontend)
await bus.reply(content=response, context=context)

# After
await self.session.chat(message, frontend)
# session.chat() handles sending via frontend
```

### Subagent Dispatch (subagent_tool.py)

Use dispatch context manager + `show_message()` for result:

```python
async with frontend.show_dispatch(calling_agent, target_agent, task):
    result = await subagent_session.chat(task, silent_frontend)

# Result shown via show_message with subagent's agent_id
await frontend.show_message(result, agent_id=target_agent)
```

## Error Handling Strategy

- All message sends wrapped in try/catch
- Errors logged at WARNING level
- Never propagate to block main loop
- Fire-and-forget semantics with observability

## Migration Path

1. Update `Frontend` base class with async methods
2. Update `SilentFrontend`, `ConsoleFrontend`, `MessageBusFrontend`
3. Update `AgentSession.chat()` to call `show_message()`
4. Update callers: `ChatLoop`, `MessageBusExecutor`, `subagent_tool`
5. Update tests to use async patterns

## Future Considerations

- MessageBus may evolve into queue-based system
- Async interface prepared for backpressure/retry logic
- `agent_id` parameter enables rich multi-agent UI
