# CLI as MessageBus Design

Treat CLI as just another channel, unified with Telegram/Discord via MessageBus abstraction.

## Architecture

```
stdin input
    │
    ▼
CliBus.receive()
    │
    ▼
InboundMessage(channel="cli", peer_id="default")
    │
    ▼
BindingTable.resolve("cli", "default")
    │
    ▼
Agent.chat()
    │
    ▼
CliBus.reply()
    │
    ▼
stdout
```

## Key Interfaces

```python
@dataclass
class InboundMessage:
    text: str
    channel: str       # "cli", "telegram", "discord"
    peer_id: str       # "default", telegram user id, etc.
    account_id: str    # "cli-local", bot account
    sender_id: str     # User identifier
    is_group: bool     # False for CLI
    raw: dict          # Platform-specific data

class CliBus(MessageBus[None]):
    """CLI implementation of MessageBus. Context type is None."""

    name = "cli"

    def __init__(self, account_id: str = "cli-local"):
        self.account_id = account_id

    def receive(self) -> InboundMessage | None:
        """Blocking read from stdin. Returns None on EOF."""

    def reply(self, content: str, context: None = None) -> None:
        """Print to stdout with formatting."""

    def is_allowed(self, context: None) -> bool:
        return True  # CLI always allowed
```

## Data Flow

1. CLI chat loop calls `CliBus.receive()` for user input
2. Produces `InboundMessage` with `channel="cli"`, `peer_id="default"`
3. `BindingTable.resolve()` maps to agent
4. `Agent.chat()` processes message
5. `CliBus.reply()` outputs response

## Integration Points

- **Location:** New module `messagebus/cli_bus.py`
- **Usage:** Update `cli/chat.py` to use `CliBus` instead of direct `ConsoleFrontend`
- **Benefit:** Unified pipeline, CLI can use routing table

## References

- claw0 s04_channels.py: `CLIChannel`, `InboundMessage`
