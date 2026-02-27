# Slash Commands Design

REPL commands for session and agent management via `/`-prefixed handlers.

## Architecture

```
CLI Input
    → starts with "/"?
        → Yes: CommandRegistry.dispatch(cmd, args, ctx)
        → No: Normal agent.chat()
```

## Key Interfaces

```python
@dataclass
class CommandResult:
    message: str | None = None
    new_messages: list[dict] | None = None
    switch_agent: str | None = None

class Command(ABC):
    name: str
    aliases: list[str] = []

    @abstractmethod
    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        pass

class CommandRegistry:
    _commands: dict[str, Command]

    def register(self, cmd: Command) -> None
    def resolve(self, input: str) -> tuple[Command, str] | None
    def dispatch(self, input: str, ctx: SharedContext) -> CommandResult | None
```

## Built-in Commands

| Command | Action |
|---------|--------|
| `/new` | Create fresh session |
| `/context` | Show token usage bar |
| `/compact` | Manually trigger context compaction |
| `/agent` | List available agents |
| `/agent:<id>` | Switch to agent |
| `/skills` | List all skills |
| `/skills:<id>` | Show skill details |
| `/skills:<id> delete` | Delete skill |
| `/crons` | List all cron jobs |
| `/crons:<id>` | Show cron details |
| `/crons:<id> delete` | Delete cron |

## Dispatch Flow

```
"/agent:cookie"
    → CommandRegistry.parse("agent:cookie")
    → (AgentCommand, "cookie")
    → AgentCommand.execute("cookie", ctx)
    → CommandResult(switch_agent="cookie")
```

## Integration Points

- **Location:** New module `cli/commands/` with `base.py`, `registry.py`, `handlers/`
- **Usage:** Import and call in `cli/chat.py` REPL loop before `agent.chat()`
- **Pattern:** Similar to `tools/registry.py` decorator pattern

## References

- claw0 s03_sessions.py: `handle_repl_command()` function
