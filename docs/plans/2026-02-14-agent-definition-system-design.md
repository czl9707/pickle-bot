# Agent Definition System Design

## Overview

Enable multi-agent support by moving agent configuration from YAML config files to file-based agent definitions. Each agent has its own directory with an `AGENT.md` file containing YAML frontmatter for settings and markdown body for the system prompt.

## Goals

- Support multiple agents with different behaviors and prompts
- Keep agent definitions editable and version-controllable
- Allow per-agent LLM overrides while sharing common config
- Simple file-based structure that can extend later

## Non-Goals

- User-defined agents / onboarding flow (deferred)
- Tool filtering per agent (all tools available to all agents)
- Agent registry / discovery (over-engineered for now)

## File Structure

```
~/.pickle-bot/
├── config.system.yaml      # default_agent, paths
├── config.user.yaml        # llm (provider, model, key)
└── agents/
    └── pickle/
        └── AGENT.md        # name, temp, tokens, prompt
```

## Agent Definition Format

`AGENT.md` uses YAML frontmatter + markdown body:

```markdown
---
name: Pickle
provider: openai        # Optional, overrides shared
model: gpt-4            # Optional, overrides shared
temperature: 0.7        # Optional
max_tokens: 4096        # Optional
---

You are pickle-bot, a helpful AI assistant...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for the agent |
| `provider` | No | LLM provider, falls back to shared config |
| `model` | No | Model name, falls back to shared config |
| `temperature` | No | Sampling temperature (default: 0.7) |
| `max_tokens` | No | Max response tokens (default: 2048) |

## Configuration Changes

### Updated Config Model

```python
class Config(BaseModel):
    workspace: Path
    llm: LLMConfig
    default_agent: str                    # Required, no default
    agents_path: Path = Path("agents")    # Resolves to ~/.pickle-bot/agents/
    logging_path: Path = Path(".logs")
    history_path: Path = Path(".history")
```

### Removed

- `AgentConfig` class
- `AgentBehaviorConfig` class

### Example config.system.yaml

```yaml
default_agent: pickle
logging_path: .logs
history_path: .history
```

## Data Models

### AgentDef

```python
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str                      # Folder name (e.g., "pickle")
    name: str                    # Display name from frontmatter
    system_prompt: str           # Markdown body
    llm: LLMConfig               # Merged LLM settings
    behavior: AgentBehaviorConfig
```

### AgentBehaviorConfig

```python
class AgentBehaviorConfig(BaseModel):
    """Agent behavior settings."""
    temperature: float = 0.7
    max_tokens: int = 2048
```

## AgentLoader

```python
class AgentLoader:
    def __init__(self, agents_dir: Path, shared_llm: LLMConfig):
        self.agents_dir = agents_dir
        self.shared_llm = shared_llm

    def load(self, agent_id: str) -> AgentDef:
        """Load agent by ID, merge with shared LLM config."""
        agent_file = self.agents_dir / agent_id / "AGENT.md"
        if not agent_file.exists():
            raise AgentNotFoundError(agent_id)

        frontmatter, body = self._parse_agent_file(agent_file)
        merged_llm = self._merge_llm_config(frontmatter)

        return AgentDef(
            id=agent_id,
            name=frontmatter.get("name", agent_id),
            system_prompt=body,
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
        )
```

### Error Handling

```python
class AgentError(Exception):
    """Base error for agent loading."""

class AgentNotFoundError(AgentError):
    """Agent folder or AGENT.md doesn't exist."""

class InvalidAgentError(AgentError):
    """Agent file is malformed."""
```

## CLI Integration

```python
@app.command()
def chat(
    agent: str | None = Option(None, "--agent", "-a", help="Agent to use"),
):
    config = Config.load(workspace_dir)

    # Use CLI flag or fall back to config default
    agent_id = agent or config.default_agent

    # Load agent definition
    loader = AgentLoader(config.agents_path, config.llm)
    agent_def = loader.load(agent_id)

    # Pass to Agent
    agent = Agent(agent_def, tools, frontend, ...)
```

**Usage:**
```bash
picklebot chat              # Uses default_agent from config
picklebot chat --agent pickle
picklebot chat -a pickle
```

## Agent Class Changes

**Before:**
```python
class Agent:
    def __init__(self, config: Config, ...):
        self.config = config
```

**After:**
```python
class Agent:
    def __init__(self, agent_def: AgentDef, tools: ToolRegistry, frontend: Frontend, ...):
        self.agent_def = agent_def
```

## Implementation Files

### New Files

- `src/picklebot/core/agent_def.py` — AgentDef, AgentBehaviorConfig models
- `src/picklebot/core/agent_loader.py` — AgentLoader, exceptions

### Modified Files

- `src/picklebot/utils/config.py` — Remove AgentConfig, add default_agent/agents_path
- `src/picklebot/core/agent.py` — Accept AgentDef instead of Config
- `src/picklebot/cli/chat.py` — Add --agent flag, use AgentLoader

## Migration

1. Create `~/.pickle-bot/agents/pickle/AGENT.md` from existing config
2. Update `~/.pickle-bot/config.system.yaml` to use new format

## Future Extensions

- Onboarding command to populate agent templates
- User-defined agents with override capability
- Per-agent tool filtering
- Agent discovery/listing command
- Additional files per agent (custom tools, context docs)
