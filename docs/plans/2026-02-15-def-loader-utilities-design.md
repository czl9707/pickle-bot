# Definition Loader Utilities Design

## Overview

Extract shared markdown parsing and discovery logic from `agent_loader`, `skill_loader`, and `cron_loader` into a common utility module.

## Problem

Three loaders share nearly identical patterns:

| Pattern | agent_loader | skill_loader | cron_loader |
|---------|--------------|--------------|-------------|
| YAML frontmatter parsing | `_parse_agent_file()` | inline (2 places) | `_parse_cron_file()` |
| Discovery scan | ❌ | `discover_skills()` | `discover_crons()` |
| NotFound error | `AgentNotFoundError` | `SkillNotFoundError` | `CronNotFoundError` |
| InvalidFormat error | `InvalidAgentError` | (uses NotFound) | `InvalidCronError` |

## Solution

### New Module: `utils/def_loader.py`

**Parsing function:**
```python
def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter + markdown body.

    Args:
        content: Raw file content

    Returns:
        Tuple of (frontmatter dict, body string)

    Example:
        >>> content = '''---
        ... name: My Agent
        ... ---
        ... System prompt here'''
        >>> frontmatter, body = parse_frontmatter(content)
        >>> frontmatter
        {'name': 'My Agent'}
        >>> body
        'System prompt here'
    """
```

**Discovery function:**
```python
def discover_definitions[T](
    path: Path,
    filename: str,
    parse_metadata: Callable[[str, dict[str, Any], str], T | None],
    logger: Logger,
) -> list[T]:
    """
    Scan directory for definition files.

    Args:
        path: Directory containing definition folders
        filename: File to look for (e.g., "AGENT.md", "SKILL.md")
        parse_metadata: Callback(def_id, frontmatter, body) -> Metadata or None
        logger: For warnings on missing/invalid files

    Returns:
        List of metadata objects from successful parses

    Example:
        >>> def parse_skill(id, fm, body):
        ...     if 'name' not in fm:
        ...         return None
        ...     return SkillMetadata(id=id, name=fm['name'], ...)
        >>> skills = discover_definitions(path, "SKILL.md", parse_skill, logger)
    """
```

**Error classes:**
```python
class DefNotFoundError(Exception):
    """Definition folder or file doesn't exist."""

    def __init__(self, kind: str, def_id: str):
        super().__init__(f"{kind.capitalize()} not found: {def_id}")
        self.kind = kind
        self.def_id = def_id


class InvalidDefError(Exception):
    """Definition file is malformed."""

    def __init__(self, kind: str, def_id: str, reason: str):
        super().__init__(f"Invalid {kind} '{def_id}': {reason}")
        self.kind = kind
        self.def_id = def_id
        self.reason = reason
```

### Refactored Loaders

All three loaders will:

1. Use `parse_frontmatter()` in their `load()` methods
2. Use generic `DefNotFoundError` / `InvalidDefError` with appropriate `kind` parameter
3. Implement discover methods via `discover_definitions()`
4. Remove private `_parse_*_file()` methods

**AgentLoader changes:**
- Remove `_parse_agent_file()` → use `parse_frontmatter()`
- Replace `AgentNotFoundError` → `DefNotFoundError("agent", agent_id)`
- Replace `InvalidAgentError` → `InvalidDefError("agent", agent_id, reason)`
- Add new `discover_agents()` method using `discover_definitions()`

**SkillLoader changes:**
- Remove inline parsing in `_parse_skill_metadata()` and `load_skill()` → use `parse_frontmatter()`
- Replace `SkillNotFoundError` → `DefNotFoundError("skill", skill_id)` and `InvalidDefError("skill", ...)`
- Refactor `discover_skills()` to use `discover_definitions()`

**CronLoader changes:**
- Remove `_parse_cron_file()` → use `parse_frontmatter()`
- Replace `CronNotFoundError` → `DefNotFoundError("cron", cron_id)`
- Replace `InvalidCronError` → `InvalidDefError("cron", cron_id, reason)`
- Refactor `discover_crons()` to use `discover_definitions()`

### No Caller Changes

External callers remain unchanged:
- `skill_tool.py` → still calls `skill_loader.discover_skills()`
- `cron_executor.py` → still calls `cron_loader.discover_crons()`

## Files Changed

| File | Action |
|------|--------|
| `src/picklebot/utils/def_loader.py` | Create new module |
| `src/picklebot/core/agent_loader.py` | Refactor to use utilities |
| `src/picklebot/core/skill_loader.py` | Refactor to use utilities |
| `src/picklebot/core/cron_loader.py` | Refactor to use utilities |
| `src/picklebot/utils/__init__.py` | Export new utilities |

## Benefits

- **DRY**: Single parsing implementation instead of three similar ones
- **Consistency**: All loaders use the same error format
- **Extensibility**: Easy to add new definition types
- **Testability**: Utilities can be unit tested independently
