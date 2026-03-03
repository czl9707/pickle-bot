# Multi-Layer Prompt System Design

## Overview

Implement a layered system prompt assembly inspired by claw0's architecture. The prompt is built dynamically each turn from multiple sources, with earlier layers having stronger influence on agent behavior.

## Layer Structure

The system prompt is assembled from 5 layers (in order):

1. **Identity** - AGENT.md body (`agent_md`)
2. **Soul** - SOUL.md (`soul_md`, optional personality traits)
3. **Bootstrap** - BOOTSTRAP.md + AGENTS.md + dynamic cron list
4. **Runtime** - Agent ID + current timestamp
5. **Channel** - Platform name hint

## File Structure

### Per-agent files
```
agents/
├── cookie/
│   ├── AGENT.md      # Frontmatter + body (agent_md)
│   └── SOUL.md       # Optional personality traits
└── pickle/
    ├── AGENT.md
    └── SOUL.md
```

### Workspace-level files
```
workspace/
├── BOOTSTRAP.md      # Guidelines for working with workspace
├── AGENTS.md         # Lists available agents
└── skills/           # Existing skills
```

## Schema Changes

### AgentDef

```python
class AgentDef(BaseModel):
    id: str
    name: str
    description: str = ""
    agent_md: str          # Renamed from system_prompt
    soul_md: str = ""      # New: content of SOUL.md (optional)
    llm: LLMConfig
    allow_skills: bool = False
    max_concurrency: int = Field(default=1, ge=1)
```

### CronDef

```python
class CronDef(BaseModel):
    id: str
    name: str
    description: str       # New: mandatory field
    agent: str
    schedule: str
    message: str
```

## PromptBuilder Class

New file: `src/picklebot/core/prompt_builder.py`

```python
class PromptBuilder:
    """Assembles system prompt from layered sources."""

    def __init__(self, workspace_path: Path, cron_loader: CronLoader):
        self.workspace_path = workspace_path
        self.cron_loader = cron_loader

    def build(self, session: "AgentSession") -> str:
        """Build the full system prompt from layers."""
        layers = []

        # Layer 1: Identity
        layers.append(session.agent.agent_def.agent_md)

        # Layer 2: Soul
        if session.agent.agent_def.soul_md:
            layers.append(f"## Personality\n\n{session.agent.agent_def.soul_md}")

        # Layer 3: Bootstrap
        bootstrap = self._load_bootstrap_context()
        if bootstrap:
            layers.append(bootstrap)

        # Layer 4: Runtime
        layers.append(self._build_runtime_context(
            session.agent.agent_def.id,
            datetime.now()
        ))

        # Layer 5: Channel
        layers.append(self._build_channel_hint(session.source))

        return "\n\n".join(layers)

    def _load_bootstrap_context(self) -> str:
        """Load BOOTSTRAP.md + AGENTS.md + cron list."""
        parts = []

        # BOOTSTRAP.md
        bootstrap_path = self.workspace_path / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            parts.append(bootstrap_path.read_text().strip())

        # AGENTS.md
        agents_path = self.workspace_path / "AGENTS.md"
        if agents_path.exists():
            parts.append(agents_path.read_text().strip())

        # Dynamic cron list
        cron_list = self._format_cron_list()
        if cron_list:
            parts.append(cron_list)

        return "\n\n".join(parts)

    def _format_cron_list(self) -> str:
        """Format crons as markdown list."""
        crons = self.cron_loader.discover_crons()
        if not crons:
            return ""

        lines = ["## Scheduled Tasks\n"]
        for cron in crons:
            lines.append(f"- **{cron.name}**: {cron.description}")
        return "\n".join(lines)

    def _build_runtime_context(self, agent_id: str, timestamp: datetime) -> str:
        """Build runtime info section."""
        return f"## Runtime\n\nAgent: {agent_id}\nTime: {timestamp.isoformat()}"

    def _build_channel_hint(self, source: EventSource) -> str:
        """Build platform hint."""
        platform = source.platform_name or "unknown"
        return f"You are responding via {platform}."
```

## Integration Changes

### SharedContext

Add `prompt_builder` field, initialized with `CronLoader` reference.

### AgentSession._build_messages()

```python
def _build_messages(self) -> list[Message]:
    system_prompt = self.shared_context.prompt_builder.build(self)
    messages: list[Message] = [{"role": "system", "content": system_prompt}]
    messages.extend(self.get_history())
    return messages
```

### AgentLoader

- Load `SOUL.md` from same folder as `AGENT.md`
- Populate `soul_md` field on AgentDef (empty string if file missing)

## Files to Modify

| File | Action |
|------|--------|
| `src/picklebot/core/prompt_builder.py` | Create |
| `src/picklebot/core/agent_loader.py` | Add `soul_md`, rename `system_prompt` → `agent_md` |
| `src/picklebot/core/cron_loader.py` | Add mandatory `description` field |
| `src/picklebot/core/context.py` | Add `prompt_builder` field |
| `src/picklebot/core/agent.py` | Update `_build_messages()` |
| `workspace/skills/cron-op/SKILL.md` | Update to require description |

## Migration Notes

- Existing AGENT.md files require no changes (body content becomes `agent_md`)
- Existing crons need `description` field added
- Tests referencing `system_prompt` need update to `agent_md`
