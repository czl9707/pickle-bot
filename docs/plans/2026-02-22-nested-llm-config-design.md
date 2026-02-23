# Nested LLM Config Design

## Overview

Refactor agent definitions to use a nested `llm:` configuration block, merging `temperature` and `max_tokens` into `LLMConfig` to eliminate the separate `AgentBehaviorConfig` class.

## Motivation

- Reduce overlap between `AgentDef` and LLM configuration
- Reuse `LLMConfig` class for all LLM-related settings
- Simplify the codebase by removing `AgentBehaviorConfig`

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config nesting | Nested `llm:` block | Matches code's `AgentDef.llm` structure |
| Backwards compatibility | None | Clean break, simpler code |
| Global config | Unchanged | Only connection params, behavior defaults in class |
| Merge strategy | Deep merge | Agent's `llm:` inherits from global `llm:` |

## Data Model Changes

### LLMConfig (src/picklebot/utils/config.py)

Add `temperature` and `max_tokens` with defaults:

```python
class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str
    model: str
    api_key: str
    api_base: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
```

### AgentDef (src/picklebot/core/agent_loader.py)

Remove `AgentBehaviorConfig` entirely. Simplified `AgentDef`:

```python
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    description: str = ""
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False
```

## Frontmatter Format

### Before (flat)

```yaml
---
name: Cookie
description: A focused task-oriented assistant
temperature: 0.3
---
```

### After (nested)

```yaml
---
name: Cookie
description: A focused task-oriented assistant
llm:
  temperature: 0.3
---
```

Agents can override any LLM field:

```yaml
---
name: Custom Agent
llm:
  provider: anthropic
  model: claude-3-opus
  temperature: 0.5
  max_tokens: 4096
---
```

## Merge Logic

Deep merge agent's `llm:` with global `config.llm`:

```python
def _merge_llm_config(self, agent_llm: dict[str, Any] | None) -> LLMConfig:
    """Deep merge agent's llm config with global defaults."""
    base = self.config.llm.model_dump()
    if agent_llm:
        base = {**base, **agent_llm}
    return LLMConfig(**base)
```

## Files Changed

| File | Change |
|------|--------|
| `src/picklebot/utils/config.py` | Add `temperature`, `max_tokens` to `LLMConfig` |
| `src/picklebot/core/agent_loader.py` | Remove `AgentBehaviorConfig`, update `AgentDef`, refactor parsing |
| `default_workspace/agents/cookie/AGENT.md` | Migrate to nested format |
| `default_workspace/agents/pickle/AGENT.md` | Migrate to nested format |
| `tests/core/test_agent_loader.py` | Update fixtures |

## API Impact

The `/agents/{id}` endpoint response will include the full `llm` object with `temperature` and `max_tokens`. This is a breaking change for any consumers expecting the old flat structure.

## Migration

No automated migration. Users must manually update their agent definitions to the nested format.
