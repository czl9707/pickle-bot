# Session History Limits Design

## Problem

Sessions currently use a hardcoded 50-message history limit in `AgentSession._build_messages()`. This is appropriate for chat scenarios (MessageBus, CLI) where context should stay lean, but limiting for background jobs (cron, subagent dispatch) that may exceed 50 messages in a single execution.

## Solution

Executor-aware history limits with a `SessionMode` enum to differentiate between chat and job contexts.

## Design

### SessionMode Enum

```python
class SessionMode(str, Enum):
    CHAT = "chat"
    JOB = "job"
```

### Config

Add two configurable limits to `Config`:

```python
chat_max_history: int = Field(default=50, gt=0)
job_max_history: int = Field(default=500, gt=0)
```

Users can override in `config.user.yaml`:

```yaml
chat_max_history: 50
job_max_history: 500
```

### Session Creation

`Agent.new_session()` requires explicit mode (no default):

```python
def new_session(self, mode: SessionMode) -> AgentSession:
```

`AgentSession` stores `max_history` at creation time, looked up from config based on mode.

### Mode Assignment

| Caller | Mode | Rationale |
|--------|------|-----------|
| `cli/chat.py` | `CHAT` | Interactive terminal chat |
| `core/messagebus_executor.py` | `CHAT` | Shared session for messaging platforms |
| `core/cron_executor.py` | `JOB` | Background scheduled tasks |
| `tools/subagent_tool.py` | `JOB` | Task-oriented subagent work |

## Files Changed

| File | Change |
|------|--------|
| `core/agent.py` | Add `SessionMode` enum, add required `mode` param to `new_session()`, `AgentSession` stores and uses `max_history` |
| `utils/config.py` | Add `chat_max_history`, `job_max_history` fields |
| `core/cron_executor.py` | Pass `mode=SessionMode.JOB` |
| `core/messagebus_executor.py` | Pass `mode=SessionMode.CHAT` |
| `cli/chat.py` | Pass `mode=SessionMode.CHAT` |
| `tools/subagent_tool.py` | Pass `mode=SessionMode.JOB` |
| `tests/core/test_session.py` | Update callers with mode |
| `tests/core/test_agent.py` | Update callers with mode |
| `tests/tools/test_subagent_tool.py` | Update mock callers with mode |
