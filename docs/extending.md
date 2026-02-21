# Extending Pickle-Bot

Guide to extending and customizing pickle-bot.

## Adding Custom Tools

Tools are functions the LLM can call to perform actions.

### Using @tool Decorator

Simplest way to create a tool:

```python
from picklebot.tools.base import tool

@tool(
    name="my_tool",
    description="Does something useful",
    parameters={
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Input text to process"
            },
            "count": {
                "type": "integer",
                "description": "Number of times to process"
            }
        },
        "required": ["input"]
    },
)
async def my_tool(input: str, count: int = 1) -> str:
    """Process input text and return result."""
    result = input * count
    return f"Processed: {result}"
```

### Parameter Schema

Use OpenAI function calling schema format:

```python
parameters={
    "type": "object",
    "properties": {
        "param_name": {
            "type": "string",  # string, integer, number, boolean, array
            "description": "What this parameter does"
        }
    },
    "required": ["param_name"]  # List of required parameters
}
```

### Tool Function Requirements

- **Async function** - Must be `async def`
- **Type hints** - Help with validation
- **Return string** - All tools return string responses
- **No side effects in signature** - Parameters come from LLM

### Registration

Tools are registered at startup:

```python
# In SharedContext initialization
registry = ToolRegistry()
registry.register(my_tool)
```

Or inject later:

```python
context.tool_registry.register(my_tool)
```

### Using BaseTool Class

For more control, inherit from BaseTool:

```python
from picklebot.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {...}

    async def execute(self, **kwargs) -> str:
        # Custom logic here
        return "result"
```

Use BaseTool when:
- Need stateful tool
- Complex initialization required
- Multiple related operations

## Adding LLM Providers

Support new LLM providers by inheriting from LLMProvider.

### Minimum Implementation

```python
from picklebot.provider.base import LLMProvider

class MyProvider(LLMProvider):
    # List of provider names (for config matching)
    provider_config_name = ["myprovider", "my_provider"]

    # That's it! Inherits chat() from base class
```

The base class handles:
- Message formatting
- Tool schema conversion
- Response parsing
- Error handling

### Provider Registration

Providers auto-register when class is defined:

```python
# Just defining the class registers it
class MyProvider(LLMProvider):
    provider_config_name = ["myprovider"]
```

Use in config:

```yaml
llm:
  provider: myprovider
  model: "myprovider/model-name"
  api_key: "your-key"
```

### Custom Chat Implementation

Override `chat()` for custom behavior:

```python
class MyProvider(LLMProvider):
    provider_config_name = ["myprovider"]

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None
    ) -> Message:
        # Custom implementation
        # Must return Message object
        return Message(...)
```

## Creating Skills

Skills are markdown files with instructions loaded on-demand.

### Skill File Format

Create `~/.pickle-bot/skills/my-skill/SKILL.md`:

```markdown
---
name: My Skill
description: Brief description for LLM to decide whether to load
---

# My Skill

Detailed instructions for the skill...

## When to Use

- Scenario 1
- Scenario 2

## Process

1. Step one
2. Step two
3. Step three

## Examples

Example usage scenarios...
```

### Skill Best Practices

**Clear description:** Help LLM decide when to load
- Good: "Turn ideas into fully formed designs through dialogue"
- Bad: "A skill for things"

**Structured instructions:** Use headings, lists, code blocks
- Process steps
- Decision criteria
- Examples

**Single purpose:** One skill, one job
- Split complex skills into multiple
- Combine simple related skills

### Enabling Skills

Add to agent frontmatter:

```markdown
---
name: My Agent
allow_skills: true
---
```

The `skill` tool will be automatically registered.

### When to Create Skills vs Tools

**Create a skill when:**
- Multi-step workflow
- Requires domain knowledge
- Structured approach needed
- Will be reused

**Create a tool when:**
- Single operation
- Technical/programmatic action
- Always available
- Simple input/output

## Creating Agents

Define specialized agents for different tasks.

### Agent File Format

Create `~/.pickle-bot/agents/my-agent/AGENT.md`:

```markdown
---
name: Code Reviewer
description: Reviews code for quality and best practices
provider: anthropic
model: claude-3-opus-20240229
temperature: 0.3
max_tokens: 4096
---

You are a code review specialist...

Your responsibilities:
1. Review code for bugs
2. Check for best practices
3. Suggest improvements

Be thorough but concise...
```

### Agent Configuration

**Required fields:**
- `name` - Display name
- `description` - Brief description (shown in subagent_dispatch)

**Optional fields:**
- `provider` - Override global LLM provider
- `model` - Override global model
- `temperature` - Sampling temperature (0-2)
- `max_tokens` - Max response length
- `allow_skills` - Enable skill tool

### System Prompt Guidelines

**Be specific:**
- Define role and responsibilities
- Set expectations for behavior
- Provide decision criteria

**Be concise:**
- Agents have token limits
- Use bullet points
- Avoid repetition

**Include context:**
- When to use this agent
- What inputs to expect
- What outputs to produce

### Agent Examples

**Memory Manager (Cookie):**
```markdown
---
name: Cookie
description: Manages long-term memories
---

You manage the user's long-term memory...

Store memories in:
- topics/ - Timeless facts
- projects/ - Project state
- daily-notes/ - Day-specific events
```

**Code Reviewer:**
```markdown
---
name: Code Reviewer
description: Reviews code for quality
temperature: 0.3
---

You review code for:
- Bugs and errors
- Security issues
- Performance problems
- Best practices
```

## Creating Cron Jobs

Schedule automated tasks with cron jobs.

### Cron File Format

Create `~/.pickle-bot/crons/my-cron/CRON.md`:

```markdown
---
name: Daily Summary
agent: pickle
schedule: "0 9 * * *"
---

Generate a daily summary of:
- Calendar events for today
- Pending tasks
- Important emails
```

### Schedule Syntax

Standard cron format: `minute hour day month weekday`

**Examples:**
- `"*/15 * * * *"` - Every 15 minutes
- `"0 9 * * *"` - Daily at 9 AM
- `"0 */2 * * *"` - Every 2 hours
- `"0 9 * * 1"` - Every Monday at 9 AM

### Cron Requirements

- **Minimum granularity:** 5 minutes
- **Fresh session:** No memory between runs
- **Sequential execution:** One job at a time
- **Server mode:** Requires `picklebot server`

### Cron Prompt Tips

**Be specific:**
- List exact tasks
- Define success criteria
- Specify output format

**Use proactive messaging:**
```markdown
---
name: Build Monitor
agent: pickle
schedule: "*/5 * * * *"
---

Check if build is failing.
If failing, use post_message tool to notify me.
```

**Keep it simple:**
- One responsibility per cron
- Clear success/failure conditions
- Actionable output

## Frontend Customization

Create custom frontends for different output modes.

### Frontend Interface

```python
from picklebot.frontend.base import Frontend

class MyFrontend(Frontend):
    async def show(self, content: str) -> None:
        """Display agent message."""
        # Your implementation

    async def show_transient(self, content: str) -> None:
        """Display temporary status."""
        # Your implementation

    async def reply(self, content: str) -> None:
        """Send reply to user."""
        # Your implementation
```

### Frontend Types

**ConsoleFrontend:** Rich terminal output
- Syntax highlighting
- Progress indicators
- Markdown rendering

**SilentFrontend:** No output
- Used for cron jobs
- Background tasks

**MessageBusFrontend:** Platform-specific output
- Routes to Telegram/Discord
- Platform context preserved

### Custom Frontend Example

```python
class LoggingFrontend(Frontend):
    def __init__(self, log_file: str):
        self.log_file = log_file

    async def show(self, content: str) -> None:
        with open(self.log_file, 'a') as f:
            f.write(f"AGENT: {content}\n")

    async def reply(self, content: str) -> None:
        with open(self.log_file, 'a') as f:
            f.write(f"REPLY: {content}\n")
        print(content)  # Also show in console
```
