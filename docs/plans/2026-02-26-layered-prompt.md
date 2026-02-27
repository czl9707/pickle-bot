# Layered Prompt Assembly Design

Dynamic system prompt assembly from files and runtime context.

## 6-Layer Architecture

```
┌─────────────────────────────────────┐
│ 1. Identity                         │  ← Agent's system_prompt (AGENT.md body)
├─────────────────────────────────────┤
│ 2. Soul                             │  ← SOUL.md (personality)
├─────────────────────────────────────┤
│ 3. Tools                            │  ← TOOLS.md (usage guidelines)
├─────────────────────────────────────┤
│ 4. Skills                           │  ← Available skills block (if enabled)
├─────────────────────────────────────┤
│ 5. Memory                           │  ← Auto-recalled context
├─────────────────────────────────────┤
│ 6. Runtime                          │  ← Agent ID, model, channel, timestamp
└─────────────────────────────────────┘
```

## Key Interfaces

```python
class PromptBuilder:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def build(
        self,
        agent: AgentDef,
        channel: str = "terminal",
        user_message: str = "",
        mode: str = "full"
    ) -> str:
        """Assemble layers into final system prompt."""

    def _load_layer(self, filename: str, max_chars: int = 20000) -> str:
        """Load and truncate a file from workspace."""

    def _build_skills_block(self, agent: AgentDef) -> str:
        """Format available skills if agent allows."""

    def _auto_recall_memory(self, query: str) -> str:
        """Search memory for relevant context."""
```

## Layer Sources

| Layer | Source | Loaded From |
|-------|--------|-------------|
| Identity | Agent's system_prompt | `agents/{id}/AGENT.md` body |
| Soul | SOUL.md | `workspace/SOUL.md` or agent override |
| Tools | TOOLS.md | `workspace/TOOLS.md` |
| Skills | Skills block | `skills/*/SKILL.md` (if `allow_skills: true`) |
| Memory | Auto-recall | TF-IDF search for relevant context |
| Runtime | Generated | Agent ID, model, channel, current time |

## Mode Variations

| Mode | Layers Included | Use Case |
|------|-----------------|----------|
| `full` | All 6 | Main agent conversations |
| `minimal` | Identity + Tools | Subagent dispatch, cron jobs |
| `none` | Identity only | Bare minimum calls |

## Example Output

```
You are Pickle, a helpful AI assistant.

## Personality

[Content from SOUL.md]

## Tool Usage Guidelines

[Content from TOOLS.md]

## Available Skills

### Skill: Brainstorming
Description: Turn ideas into designs...

## Memory

### Recalled Memories
- [2024-01-15] User prefers concise responses...

## Runtime Context

- Agent ID: pickle
- Model: claude-sonnet-4-20250514
- Channel: telegram
- Current time: 2026-02-26 14:30 UTC
```

## Integration Points

- **Location:** New module `core/prompt.py`
- **Usage:** Call in `Agent.chat()` before LLM call
- **Replaces:** Static `AgentDef.system_prompt` as sole source

## References

- claw0 s06_intelligence.py: `build_system_prompt()`, `BootstrapLoader`
