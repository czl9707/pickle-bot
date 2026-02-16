# Skill System Design

**Date:** 2026-02-15
**Status:** Approved
**Approach:** Single Skill Tool with Lazy Loading

## Overview

The skill system allows users to define specialized capabilities in markdown files that can be loaded on-demand by the LLM through a tool interface. Skills are user-editable, stored globally, and presented to the LLM via a special "skill" tool.

## Architecture

### Components

1. **Skill Files** - User-defined `SKILL.md` files in `~/.pickle-bot/skills/[name]/SKILL.md`
2. **SkillLoader** - Component that scans, parses, and validates skill definitions
3. **Skill Tool** - Conditional tool that presents available skills and loads content on invocation

### Data Flow

```
Agent Initialization → SkillLoader scans skills/ → Skill metadata cached
         ↓
Agent with allow_skills=true → Skill tool registered with enum of skill names
         ↓
LLM calls skill tool → Skill content loaded from SKILL.md → Returned as tool result
```

## Skill Definition Format

### File Structure

```
~/.pickle-bot/skills/
├── brainstorming/
│   └── SKILL.md
├── debugging/
│   └── SKILL.md
└── code-review/
    └── SKILL.md
```

### SKILL.md Format

```markdown
---
name: brainstorming
description: Turn ideas into fully formed designs through collaborative dialogue
---

# Brainstorming Ideas Into Designs

## Overview
Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

[rest of skill instructions...]
```

### Validation Rules

- Frontmatter must have `name` and `description` fields (both required)
- `name` should be human-readable (e.g., "Brainstorming Ideas")
- `description` should be concise (used by LLM to decide whether to load skill)
- Body contains full skill instructions

### Pydantic Models

```python
class SkillMetadata(BaseModel):
    """Lightweight skill info for discovery."""
    id: str  # directory name
    name: str  # from frontmatter
    description: str  # from frontmatter


class SkillDef(BaseModel):
    """Loaded skill definition."""
    id: str
    name: str
    description: str
    content: str  # full markdown body

    class Config:
        extra = "forbid"
```

## SkillLoader Component

**Location:** `src/picklebot/core/skill_loader.py`

### Responsibilities

- Scan `~/.pickle-bot/skills/` directory
- Parse SKILL.md files with YAML frontmatter
- Validate skill definitions
- Provide skill discovery and loading APIs

### Key Methods

```python
class SkillLoader:
    def __init__(self, skills_path: Path):
        self.skills_path = skills_path

    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory, return list of valid SkillMetadata."""

    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill content by ID."""

    def validate_skill(self, skill_path: Path) -> bool:
        """Validate a SKILL.md file, return True if valid."""
```

### Error Handling

- `discover_skills()`: Skip invalid skills with warnings, return only valid ones
- `load_skill()`: Raise `SkillNotFoundError` if skill doesn't exist
- Log warnings for malformed SKILL.md files (graceful degradation)

## AgentDef Changes

### Add `allow_skills` Field

```python
class AgentDef(BaseModel):
    """Loaded agent definition."""
    id: str
    name: str
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False  # New field, defaults to False

    class Config:
        extra = "forbid"
```

### AGENT.md Example

```markdown
---
name: General Assistant
provider: openai
model: gpt-4
allow_skills: true
---

You are a helpful assistant with access to specialized skills...
```

### Integration

- `AgentLoader` parses `allow_skills` from YAML frontmatter (if present, defaults to `False`)
- Backwards compatible - existing agents without this field continue working normally

## Skill Tool Implementation

### Tool Factory

```python
from picklebot.tools.base import tool

def create_skill_tool(skill_metadata: list[SkillMetadata], skill_loader: SkillLoader):
    """Factory function to create skill tool with dynamic schema."""

    # Build XML description of available skills
    skills_xml = "<skills>\n"
    for meta in skill_metadata:
        skills_xml += f'  <skill name="{meta.name}">{meta.description}</skill>\n'
    skills_xml += "</skills>"

    # Build enum of skill IDs
    skill_enum = [meta.id for meta in skill_metadata]

    @tool(
        name="skill",
        description=f"Load and invoke a specialized skill. {skills_xml}",
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": skill_enum,
                    "description": "The name of the skill to load"
                }
            },
            "required": ["skill_name"]
        }
    )
    async def skill_tool(skill_name: str) -> str:
        """Load and return skill content."""
        try:
            skill_def = skill_loader.load_skill(skill_name)
            return skill_def.content
        except SkillNotFoundError:
            return f"Error: Skill '{skill_name}' not found. It may have been removed or is unavailable."
        except Exception as e:
            return f"Error loading skill '{skill_name}': {e}"

    return skill_tool
```

### Design Points

- **Dynamic schema** - Tool description and enum are built from available skills
- **Factory pattern** - Create tool instance with skill metadata injected
- **Conditionally registered** - Only added to ToolRegistry if `allow_skills: true`
- **XML format** - Skills listed as XML in description for LLM comprehension
- **Single parameter** - Just `skill_name`, no additional context needed

## Agent Integration

### Agent Constructor

```python
class Agent:
    def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
        self.agent_def = agent_def
        self.context = context
        self.tools = ToolRegistry.with_builtins()
        self.llm = LLMProvider.from_config(agent_def.llm)

        # Add skill tool if allowed
        if agent_def.allow_skills:
            self._register_skill_tool()

    def _register_skill_tool(self) -> None:
        """Register the skill tool if skills are available."""
        skill_loader = SkillLoader(self.context.config.skills_path)
        skill_metadata = skill_loader.discover_skills()

        if skill_metadata:
            skill_tool = create_skill_tool(skill_metadata, skill_loader)
            self.tools.register(skill_tool)
```

### Key Points

- Skill tool registered once per Agent instance (not per session)
- SkillLoader scans skills directory at agent initialization
- Only registered if `allow_skills: true` AND skills exist
- Skill metadata cached in tool closure for agent lifetime
- Multiple sessions from same agent share the same skill tool instance

## Error Handling

### Custom Exception

```python
class SkillNotFoundError(Exception):
    """Raised when a skill is not found."""
    pass
```

### SkillLoader Error Handling

```python
class SkillLoader:
    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory, return list of valid SkillMetadata."""
        if not self.skills_path.exists():
            logger.warning(f"Skills directory not found: {self.skills_path}")
            return []

        skills = []
        for skill_dir in self.skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                logger.warning(f"No SKILL.md found in {skill_dir.name}")
                continue

            try:
                metadata = self._parse_skill_metadata(skill_file)
                skills.append(metadata)
            except Exception as e:
                logger.warning(f"Invalid skill {skill_dir.name}: {e}")
                continue

        return skills
```

### Graceful Degradation Summary

- Missing skills directory → log warning, return empty list (no skill tool registered)
- Invalid SKILL.md → log warning, skip that skill, continue with others
- Skill not found at runtime → return helpful error message to LLM
- Agent continues working even if skill system has issues

## Configuration

### Config Model Updates

```python
class Config(BaseModel):
    """Application configuration."""
    default_agent: str = "default"
    history_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "history")
    agents_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "agents")
    skills_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "skills")  # New
    llm: LLMConfig = Field(default_factory=LLMConfig)
```

### Default Directory Structure

```
~/.pickle-bot/
├── config.system.yaml
├── config.user.yaml
├── agents/
│   └── [agent-name]/AGENT.md
├── skills/              # New
│   ├── brainstorming/
│   │   └── SKILL.md
│   └── debugging/
│       └── SKILL.md
└── history/
    └── sessions/
```

### User Override Example

```yaml
# ~/.pickle-bot/config.user.yaml
skills_path: /custom/path/to/skills
```

## Implementation Checklist

- [ ] Create `SkillMetadata` and `SkillDef` Pydantic models
- [ ] Implement `SkillLoader` class with `discover_skills()` and `load_skill()` methods
- [ ] Add `allow_skills: bool` field to `AgentDef` model
- [ ] Update `AgentLoader` to parse `allow_skills` from frontmatter
- [ ] Create `create_skill_tool()` factory function
- [ ] Update `Agent.__init__()` to conditionally register skill tool
- [ ] Add `skills_path` to `Config` model with default path
- [ ] Add `SkillNotFoundError` custom exception
- [ ] Add logging for skill discovery and loading operations
- [ ] Write unit tests for SkillLoader
- [ ] Write integration tests for skill tool execution
- [ ] Update documentation with skill system usage guide
