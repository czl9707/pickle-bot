# Message Routing Table Design

Flexible routing from (channel, peer) to agent based on config-defined bindings.

## Architecture

```
InboundMessage (channel, peer_id)
        │
        ▼
   BindingTable.resolve()
        │
        ▼
   agent_id
        │
        ▼
   build_session_key(agent_id, channel, peer_id)
```

## Simplified Tiers (most specific wins)

| Tier | Match Key | Example |
|------|-----------|---------|
| 1 | peer_id | `telegram:123456` → agent:cookie |
| 2 | channel | `telegram` → agent:pickle |
| 3 | default | `*` → agent:pickle |

## Key Interfaces

```python
@dataclass
class Binding:
    agent_id: str
    match_key: str    # "peer_id" | "channel" | "default"
    match_value: str

class BindingTable:
    def __init__(self):
        self._bindings: list[Binding] = []

    @classmethod
    def from_config(cls, config: Config) -> "BindingTable":
        """Load bindings from config.routing.bindings."""

    def add(self, binding: Binding) -> None:
        """Add binding, keep sorted by tier."""

    def resolve(self, channel: str, peer_id: str) -> str:
        """Walk tiers, return matched agent_id or default."""

def build_session_key(agent_id: str, channel: str, peer_id: str, dm_scope: str = "per-peer") -> str:
    """Build session key: agent:{id}:direct:{channel}:{peer_id}"""
```

## Config Format

```yaml
routing:
  bindings:
    - agent: cookie
      match: peer_id
      value: "telegram:123456"
    - agent: pickle
      match: channel
      value: "telegram"
    - agent: pickle
      match: default
```

## Integration Points

- **Location:** New module `core/routing.py`
- **Usage:** `MessageBusWorker` resolves route before dispatching to `AgentWorker`
- **Config:** Load at startup in `SharedContext`

## References

- claw0 s05_gateway_routing.py: `BindingTable`, `Binding`, `build_session_key`
