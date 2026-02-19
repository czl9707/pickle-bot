# Template Variable Substitution

## Problem

Cookie agent's AGENT.md refers to "the configured memories_path" but doesn't know the actual path. The AgentLoader reads markdown body as-is without any template substitution, so agents cannot reference dynamic paths.

## Solution

Add a `substitute_template()` helper function in `def_loader.py` that replaces `{{variable}}` placeholders with config path values. AgentLoader will call this when parsing agent definitions.

## Available Variables

Only path-related variables (no sensitive config like API keys):

- `workspace` - e.g., `/home/user/.pickle-bot`
- `agents_path` - e.g., `/home/user/.pickle-bot/agents`
- `skills_path` - e.g., `/home/user/.pickle-bot/skills`
- `crons_path` - e.g., `/home/user/.pickle-bot/crons`
- `memories_path` - e.g., `/home/user/.pickle-bot/memories`
- `history_path` - e.g., `/home/user/.pickle-bot/.history`

## Implementation

### 1. New helper function in `def_loader.py`

```python
def substitute_template(body: str, variables: dict[str, str]) -> str:
    """
    Replace {{variable}} placeholders in template body.

    Args:
        body: Template string with {{variable}} placeholders
        variables: Dict of variable names to values

    Returns:
        Body with all placeholders replaced
    """
    result = body
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result
```

### 2. Changes to AgentLoader

Add workspace to constructor and template substitution in parsing:

```python
class AgentLoader:
    def __init__(self, agents_path: Path, shared_llm: LLMConfig, workspace: Path):
        self.agents_path = agents_path
        self.shared_llm = shared_llm
        self.workspace = workspace

    @staticmethod
    def from_config(config: Config) -> "AgentLoader":
        return AgentLoader(config.agents_path, config.llm, config.workspace)

    def _get_template_variables(self) -> dict[str, str]:
        """Get template variables for agent definitions."""
        return {
            "workspace": str(self.workspace),
            "agents_path": str(self.agents_path),
            "skills_path": str(self.workspace / "skills"),
            "crons_path": str(self.workspace / "crons"),
            "memories_path": str(self.workspace / "memories"),
            "history_path": str(self.workspace / ".history"),
        }

    def _parse_agent_def(self, def_id: str, frontmatter: dict, body: str) -> AgentDef:
        variables = self._get_template_variables()
        body = substitute_template(body, variables)
        # ... rest of existing parsing logic
```

## Usage Example

**Before (Cookie AGENT.md):**
```markdown
Memories are stored in markdown files at the configured memories_path...
```

**After (Cookie AGENT.md):**
```markdown
Memories are stored in markdown files at `{{memories_path}}` with three axes:

- **topics/** - Timeless facts about the user
- **projects/** - Project state and context
- **daily-notes/** - Day-specific events

Navigate to `{{memories_path}}/topics/` for user facts.
```

## Testing

- Unit tests for `substitute_template()`:
  - Single variable replacement
  - Multiple variables
  - Missing variables (pass through unchanged)
  - No variables present

- Integration test verifying AgentLoader produces correct system_prompt with substituted paths

## Future Extensibility

The `substitute_template()` function in `def_loader.py` is a shared utility. SkillLoader and CronLoader can use it in the future if needed by passing appropriate variable dicts.
