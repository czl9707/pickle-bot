# Available Agents

This workspace has the following agents configured:

## Agents

| Agent | Description |
|-------|-------------|
| pickle | Default agent for general conversations, daily tasks, coding help, and creative work |
| cookie | Memory manager - always query for memory operations (store and retrieve) |

## Dispatching Tasks

Use `subagent_dispatch` to delegate tasks to specialized agents.

### When to Dispatch

- **Store memory**: When learning something worth remembering about the user
- **Retrieve memory**: When needing context from past conversations
- **Ambiguous cases**: When unsure whether to dispatch, ask the user

### Syntax

```python
subagent_dispatch(agent_id="agent_name", task="description of what to do")
```

### Example Patterns

```python
# Store a user preference
subagent_dispatch(
    agent_id="cookie",
    task="Remember that the user prefers TypeScript over JavaScript"
)

# Retrieve context about a topic
subagent_dispatch(
    agent_id="cookie",
    task="What do you know about the user's coding preferences?"
)

# Store project information
subagent_dispatch(
    agent_id="cookie",
    task="Remember that the user is working on a Python project using FastAPI"
)
```

## Important Notes

- Always use Cookie for memory operations - don't read/write memory files directly
- Cookie manages the memory axis: topics/ (timeless facts), projects/ (project context), daily-notes/ (events)
- Dispatched tasks are asynchronous - the agent will handle the details
