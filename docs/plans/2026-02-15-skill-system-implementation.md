# Skill System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a skill system that allows agents to load on-demand capabilities from user-defined SKILL.md files through a special tool interface.

**Architecture:** Skills are defined in markdown files with YAML frontmatter, discovered by SkillLoader at agent initialization, and presented to the LLM via a single "skill" tool with dynamic schema. Skill content is lazy-loaded and returned as tool results.

**Tech Stack:** Python 3.x, Pydantic for models, YAML frontmatter parsing, existing tool system

---

## Task 1: Create Skill Models

**Files:**
- Create: `src/picklebot/core/skill_def.py`

**Step 1: Write the failing test**

Create `tests/core/test_skill_def.py`:

```python
"""Tests for skill definition models."""
import pytest
from picklebot.core.skill_def import SkillMetadata, SkillDef


def test_skill_metadata_creation():
    """Test SkillMetadata can be created with required fields."""
    metadata = SkillMetadata(
        id="brainstorming",
        name="Brainstorming Ideas",
        description="Turn ideas into designs"
    )
    assert metadata.id == "brainstorming"
    assert metadata.name == "Brainstorming Ideas"
    assert metadata.description == "Turn ideas into designs"


def test_skill_def_creation():
    """Test SkillDef can be created with content."""
    skill_def = SkillDef(
        id="debugging",
        name="Systematic Debugging",
        description="Fix bugs systematically",
        content="# Debugging\n\nSteps to debug..."
    )
    assert skill_def.id == "debugging"
    assert skill_def.content == "# Debugging\n\nSteps to debug..."


def test_skill_metadata_forbids_extra_fields():
    """Test SkillMetadata rejects extra fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SkillMetadata(
            id="test",
            name="Test",
            description="Test skill",
            extra_field="not allowed"
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_skill_def.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.skill_def'"

**Step 3: Write minimal implementation**

Create `src/picklebot/core/skill_def.py`:

```python
"""Skill definition models."""
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Lightweight skill info for discovery."""
    id: str
    name: str
    description: str

    class Config:
        extra = "forbid"


class SkillDef(BaseModel):
    """Loaded skill definition."""
    id: str
    name: str
    description: str
    content: str

    class Config:
        extra = "forbid"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_skill_def.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/skill_def.py tests/core/test_skill_def.py
git commit -m "feat(core): add SkillMetadata and SkillDef models"
```

---

## Task 2: Create SkillNotFoundError Exception

**Files:**
- Create: `src/picklebot/core/exceptions.py`

**Step 1: Write the failing test**

Create `tests/core/test_exceptions.py`:

```python
"""Tests for custom exceptions."""
import pytest
from picklebot.core.exceptions import SkillNotFoundError


def test_skill_not_found_error_can_be_raised():
    """Test SkillNotFoundError can be raised with message."""
    with pytest.raises(SkillNotFoundError) as exc_info:
        raise SkillNotFoundError("Skill 'test' not found")

    assert str(exc_info.value) == "Skill 'test' not found"


def test_skill_not_found_error_is_exception():
    """Test SkillNotFoundError is an Exception."""
    assert issubclass(SkillNotFoundError, Exception)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_exceptions.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.exceptions'"

**Step 3: Write minimal implementation**

Create `src/picklebot/core/exceptions.py`:

```python
"""Custom exceptions for picklebot."""


class SkillNotFoundError(Exception):
    """Raised when a skill is not found."""
    pass
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_exceptions.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/exceptions.py tests/core/test_exceptions.py
git commit -m "feat(core): add SkillNotFoundError exception"
```

---

## Task 3: Implement SkillLoader - Discovery

**Files:**
- Create: `src/picklebot/core/skill_loader.py`
- Modify: `src/picklebot/core/__init__.py`
- Test: `tests/core/test_skill_loader.py`

**Step 1: Write the failing test**

Create `tests/core/test_skill_loader.py`:

```python
"""Tests for SkillLoader."""
import pytest
from pathlib import Path
from picklebot.core.skill_loader import SkillLoader
from picklebot.core.skill_def import SkillMetadata


def test_discover_skills_empty_directory(tmp_path):
    """Test discover_skills returns empty list for empty directory."""
    loader = SkillLoader(tmp_path)
    skills = loader.discover_skills()
    assert skills == []


def test_discover_skills_missing_directory(tmp_path):
    """Test discover_skills handles missing directory gracefully."""
    missing_dir = tmp_path / "nonexistent"
    loader = SkillLoader(missing_dir)
    skills = loader.discover_skills()
    assert skills == []


def test_discover_skills_valid_skill(tmp_path):
    """Test discover_skills finds valid skill."""
    # Create skill directory and file
    skill_dir = tmp_path / "brainstorming"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Brainstorming Ideas
description: Turn ideas into designs
---

# Brainstorming
Content here...
""")

    loader = SkillLoader(tmp_path)
    skills = loader.discover_skills()

    assert len(skills) == 1
    assert skills[0].id == "brainstorming"
    assert skills[0].name == "Brainstorming Ideas"
    assert skills[0].description == "Turn ideas into designs"


def test_discover_skills_skips_invalid_skill(tmp_path, caplog):
    """Test discover_skills skips invalid skills with warning."""
    # Create valid skill
    valid_dir = tmp_path / "valid-skill"
    valid_dir.mkdir()
    valid_file = valid_dir / "SKILL.md"
    valid_file.write_text("""---
name: Valid Skill
description: A valid skill
---
Content
""")

    # Create invalid skill (missing description)
    invalid_dir = tmp_path / "invalid-skill"
    invalid_dir.mkdir()
    invalid_file = invalid_dir / "SKILL.md"
    invalid_file.write_text("""---
name: Invalid Skill
---
Content
""")

    loader = SkillLoader(tmp_path)
    skills = loader.discover_skills()

    # Should only return valid skill
    assert len(skills) == 1
    assert skills[0].id == "valid-skill"
    # Should log warning about invalid skill
    assert "invalid-skill" in caplog.text


def test_discover_skills_skips_non_directories(tmp_path):
    """Test discover_skills skips files that aren't directories."""
    # Create a file (not a directory)
    file_path = tmp_path / "not-a-directory.md"
    file_path.write_text("content")

    loader = SkillLoader(tmp_path)
    skills = loader.discover_skills()

    assert skills == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_skill_loader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.skill_loader'"

**Step 3: Write minimal implementation**

Create `src/picklebot/core/skill_loader.py`:

```python
"""Skill loader for discovering and loading skills."""
import logging
from pathlib import Path
from typing import Optional

import yaml

from picklebot.core.skill_def import SkillDef, SkillMetadata
from picklebot.core.exceptions import SkillNotFoundError

logger = logging.getLogger(__name__)


class SkillLoader:
    """Load and manage skill definitions from filesystem."""

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path

    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory and return list of valid SkillMetadata."""
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

            metadata = self._parse_skill_metadata(skill_file)
            if metadata:
                skills.append(metadata)

        return skills

    def _parse_skill_metadata(self, skill_file: Path) -> Optional[SkillMetadata]:
        """Parse skill metadata from SKILL.md file."""
        try:
            content = skill_file.read_text()

            # Split frontmatter and body
            if not content.startswith("---"):
                logger.warning(f"No frontmatter in {skill_file}")
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                logger.warning(f"Invalid frontmatter format in {skill_file}")
                return None

            frontmatter_str = parts[1].strip()
            frontmatter = yaml.safe_load(frontmatter_str)

            # Validate required fields
            if "name" not in frontmatter or "description" not in frontmatter:
                logger.warning(f"Missing required fields in {skill_file}")
                return None

            skill_id = skill_file.parent.name
            return SkillMetadata(
                id=skill_id,
                name=frontmatter["name"],
                description=frontmatter["description"]
            )
        except Exception as e:
            logger.warning(f"Failed to parse skill {skill_file}: {e}")
            return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_skill_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/skill_loader.py tests/core/test_skill_loader.py
git commit -m "feat(core): add SkillLoader with discover_skills method"
```

---

## Task 4: Implement SkillLoader - Load Skill

**Files:**
- Modify: `src/picklebot/core/skill_loader.py`
- Modify: `tests/core/test_skill_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_skill_loader.py`:

```python
from picklebot.core.exceptions import SkillNotFoundError


def test_load_skill_returns_full_content(tmp_path):
    """Test load_skill returns SkillDef with full content."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_content = """---
name: Test Skill
description: A test skill
---

# Test Skill

This is the skill content.
More content here.
"""
    skill_file.write_text(skill_content)

    loader = SkillLoader(tmp_path)
    skill_def = loader.load_skill("test-skill")

    assert skill_def.id == "test-skill"
    assert skill_def.name == "Test Skill"
    assert skill_def.description == "A test skill"
    assert "# Test Skill" in skill_def.content
    assert "This is the skill content." in skill_def.content


def test_load_skill_raises_not_found(tmp_path):
    """Test load_skill raises SkillNotFoundError for missing skill."""
    loader = SkillLoader(tmp_path)

    with pytest.raises(SkillNotFoundError):
        loader.load_skill("nonexistent-skill")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_skill_loader.py::test_load_skill_returns_full_content -v`
Expected: FAIL with "AttributeError: 'SkillLoader' object has no attribute 'load_skill'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/core/skill_loader.py`:

```python
    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill definition by ID.

        Args:
            skill_id: The skill directory name

        Returns:
            SkillDef with full content

        Raises:
            SkillNotFoundError: If skill doesn't exist or is invalid
        """
        skill_dir = self.skills_path / skill_id
        if not skill_dir.exists() or not skill_dir.is_dir():
            raise SkillNotFoundError(f"Skill '{skill_id}' not found")

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise SkillNotFoundError(f"Skill '{skill_id}' has no SKILL.md")

        try:
            content = skill_file.read_text()

            # Split frontmatter and body
            if not content.startswith("---"):
                raise SkillNotFoundError(f"Skill '{skill_id}' has invalid format")

            parts = content.split("---", 2)
            if len(parts) < 3:
                raise SkillNotFoundError(f"Skill '{skill_id}' has invalid format")

            frontmatter_str = parts[1].strip()
            frontmatter = yaml.safe_load(frontmatter_str)
            body = parts[2].strip()

            # Validate required fields
            if "name" not in frontmatter or "description" not in frontmatter:
                raise SkillNotFoundError(f"Skill '{skill_id}' missing required fields")

            return SkillDef(
                id=skill_id,
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=body
            )
        except SkillNotFoundError:
            raise
        except Exception as e:
            raise SkillNotFoundError(f"Failed to load skill '{skill_id}': {e}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_skill_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/skill_loader.py tests/core/test_skill_loader.py
git commit -m "feat(core): add load_skill method to SkillLoader"
```

---

## Task 5: Add allow_skills to AgentDef

**Files:**
- Modify: `src/picklebot/core/agent_def.py`
- Modify: `tests/core/test_agent_def.py` (if exists)

**Step 1: Write the failing test**

Create or add to `tests/core/test_agent_def.py`:

```python
"""Tests for AgentDef."""
import pytest
from picklebot.core.agent_def import AgentDef
from picklebot.utils.config import LLMConfig


def test_agent_def_defaults():
    """Test AgentDef has default values."""
    agent_def = AgentDef(
        id="test",
        name="Test Agent",
        system_prompt="You are a test agent",
        llm=LLMConfig()
    )
    assert agent_def.allow_skills is False


def test_agent_def_accepts_allow_skills():
    """Test AgentDef can have allow_skills set."""
    agent_def = AgentDef(
        id="test",
        name="Test Agent",
        system_prompt="You are a test agent",
        llm=LLMConfig(),
        allow_skills=True
    )
    assert agent_def.allow_skills is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_def.py -v`
Expected: FAIL with error about `allow_skills` field not existing

**Step 3: Write minimal implementation**

Modify `src/picklebot/core/agent_def.py`:

Add `allow_skills: bool = False` field to the AgentDef model:

```python
class AgentDef(BaseModel):
    """Loaded agent definition."""
    id: str
    name: str
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False  # New field

    class Config:
        extra = "forbid"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_def.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_def.py tests/core/test_agent_def.py
git commit -m "feat(core): add allow_skills field to AgentDef"
```

---

## Task 6: Update AgentLoader to Parse allow_skills

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent_loader.py`:

```python
def test_load_agent_with_allow_skills(tmp_path):
    """Test AgentLoader parses allow_skills from frontmatter."""
    agent_dir = tmp_path / "test-agent"
    agent_dir.mkdir()
    agent_file = agent_dir / "AGENT.md"
    agent_file.write_text("""---
name: Test Agent
allow_skills: true
---

System prompt here.
""")

    loader = AgentLoader(tmp_path, LLMConfig())
    agent_def = loader.load("test-agent")

    assert agent_def.allow_skills is True


def test_load_agent_without_allow_skills_defaults_false(tmp_path):
    """Test AgentLoader defaults allow_skills to False."""
    agent_dir = tmp_path / "test-agent"
    agent_dir.mkdir()
    agent_file = agent_dir / "AGENT.md"
    agent_file.write_text("""---
name: Test Agent
---

System prompt here.
""")

    loader = AgentLoader(tmp_path, LLMConfig())
    agent_def = loader.load("test-agent")

    assert agent_def.allow_skills is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_load_agent_with_allow_skills -v`
Expected: FAIL - test will likely pass if AgentDef already has the field, but verify the loader passes it through

**Step 3: Verify implementation**

Check `src/picklebot/core/agent_loader.py` to ensure it passes `allow_skills` from frontmatter when constructing AgentDef. The loader should already handle this if it's merging frontmatter data into AgentDef construction, but verify.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "test(core): add tests for allow_skills in AgentLoader"
```

---

## Task 7: Add skills_path to Config

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `tests/utils/test_config.py` (if exists)

**Step 1: Write the failing test**

Create or add to `tests/utils/test_config.py`:

```python
"""Tests for Config."""
from pathlib import Path
from picklebot.utils.config import Config


def test_config_has_skills_path_default():
    """Test Config has skills_path with default value."""
    config = Config()
    assert config.skills_path == Path.home() / ".pickle-bot" / "skills"


def test_config_accepts_custom_skills_path():
    """Test Config can accept custom skills_path."""
    config = Config(skills_path=Path("/custom/skills"))
    assert config.skills_path == Path("/custom/skills")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: FAIL with error about `skills_path` field not existing

**Step 3: Write minimal implementation**

Modify `src/picklebot/utils/config.py`:

Add `skills_path` field to Config model:

```python
class Config(BaseModel):
    """Application configuration."""
    default_agent: str = "default"
    history_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "history")
    agents_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "agents")
    skills_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "skills")  # New
    llm: LLMConfig = Field(default_factory=LLMConfig)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(utils): add skills_path to Config model"
```

---

## Task 8: Create Skill Tool Factory

**Files:**
- Create: `src/picklebot/tools/skill_tool.py`
- Test: `tests/tools/test_skill_tool.py`

**Step 1: Write the failing test**

Create `tests/tools/test_skill_tool.py`:

```python
"""Tests for skill tool factory."""
import pytest
from pathlib import Path
from picklebot.tools.skill_tool import create_skill_tool
from picklebot.core.skill_def import SkillMetadata
from picklebot.core.skill_loader import SkillLoader


@pytest.mark.asyncio
async def test_create_skill_tool_returns_callable():
    """Test create_skill_tool returns a callable tool function."""
    skill_metadata = [
        SkillMetadata(id="test", name="Test", description="A test skill")
    ]
    loader = SkillLoader(Path("/fake/path"))

    tool_func = create_skill_tool(skill_metadata, loader)
    assert callable(tool_func)


@pytest.mark.asyncio
async def test_skill_tool_has_correct_schema(tmp_path):
    """Test skill tool has correct schema with enum and description."""
    # Create test skill
    skill_dir = tmp_path / "brainstorming"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Brainstorming
description: Turn ideas into designs
---

Content here.
""")

    skill_metadata = [
        SkillMetadata(id="brainstorming", name="Brainstorming", description="Turn ideas into designs")
    ]
    loader = SkillLoader(tmp_path)

    tool_func = create_skill_tool(skill_metadata, loader)

    # Check tool has metadata
    assert hasattr(tool_func, '_tool_metadata')
    metadata = tool_func._tool_metadata
    assert metadata.name == "skill"
    assert "brainstorming" in metadata.description.lower()
    assert "<skills>" in metadata.description


@pytest.mark.asyncio
async def test_skill_tool_loads_content(tmp_path):
    """Test skill tool loads and returns skill content."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_content = """---
name: Test Skill
description: A test skill
---

# Test Skill
This is the content.
"""
    skill_file.write_text(skill_content)

    skill_metadata = [
        SkillMetadata(id="test-skill", name="Test Skill", description="A test skill")
    ]
    loader = SkillLoader(tmp_path)

    tool_func = create_skill_tool(skill_metadata, loader)
    result = await tool_func(skill_name="test-skill")

    assert "# Test Skill" in result
    assert "This is the content." in result


@pytest.mark.asyncio
async def test_skill_tool_handles_missing_skill(tmp_path):
    """Test skill tool returns error for missing skill."""
    skill_metadata = []
    loader = SkillLoader(tmp_path)

    tool_func = create_skill_tool(skill_metadata, loader)
    result = await tool_func(skill_name="nonexistent")

    assert "Error" in result
    assert "nonexistent" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_skill_tool.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.tools.skill_tool'"

**Step 3: Write minimal implementation**

Create `src/picklebot/tools/skill_tool.py`:

```python
"""Skill tool factory for creating dynamic skill tool."""
from pathlib import Path
from picklebot.tools.base import tool
from picklebot.core.skill_def import SkillMetadata
from picklebot.core.skill_loader import SkillLoader


def create_skill_tool(skill_metadata: list[SkillMetadata], skill_loader: SkillLoader):
    """Factory function to create skill tool with dynamic schema.

    Args:
        skill_metadata: List of available skill metadata
        skill_loader: SkillLoader instance for loading skill content

    Returns:
        Async tool function for loading skills
    """
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
        """Load and return skill content.

        Args:
            skill_name: The ID of the skill to load

        Returns:
            Skill content or error message
        """
        try:
            skill_def = skill_loader.load_skill(skill_name)
            return skill_def.content
        except Exception as e:
            return f"Error: Skill '{skill_name}' not found. It may have been removed or is unavailable."

    return skill_tool
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_skill_tool.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/skill_tool.py tests/tools/test_skill_tool.py
git commit -m "feat(tools): add create_skill_tool factory function"
```

---

## Task 9: Integrate Skill Tool into Agent

**Files:**
- Modify: `src/picklebot/core/agent.py`
- Test: `tests/core/test_agent.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.agent_def import AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


def test_agent_registers_skill_tool_when_allowed(tmp_path):
    """Test Agent registers skill tool when allow_skills is True."""
    # Setup config with skills path
    skills_path = tmp_path / "skills"
    skills_path.mkdir()
    config = Config(skills_path=skills_path)

    # Create a test skill
    skill_dir = skills_path / "test-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Test Skill
description: A test skill
---
Content
""")

    # Create agent with allow_skills
    agent_def = AgentDef(
        id="test",
        name="Test Agent",
        system_prompt="Test",
        llm=LLMConfig(),
        allow_skills=True
    )
    context = SharedContext(config)
    agent = Agent(agent_def, context)

    # Check skill tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names


def test_agent_skips_skill_tool_when_not_allowed(tmp_path):
    """Test Agent does not register skill tool when allow_skills is False."""
    config = Config()
    agent_def = AgentDef(
        id="test",
        name="Test Agent",
        system_prompt="Test",
        llm=LLMConfig(),
        allow_skills=False
    )
    context = SharedContext(config)
    agent = Agent(agent_def, context)

    # Check skill tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_agent_registers_skill_tool_when_allowed -v`
Expected: FAIL - skill tool not registered

**Step 3: Write minimal implementation**

Modify `src/picklebot/core/agent.py`:

Add imports at top:
```python
from picklebot.core.skill_loader import SkillLoader
from picklebot.tools.skill_tool import create_skill_tool
```

Add to `Agent.__init__`:
```python
def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
    self.agent_def = agent_def
    self.context = context
    # tools currently is initialized within Agent class.
    # This is intentional, in case agent will have its own tool registry config later.
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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "feat(core): integrate skill tool into Agent initialization"
```

---

## Task 10: Create Example Skill Files

**Files:**
- Create: `~/.pickle-bot/skills/brainstorming/SKILL.md`

**Step 1: Create skills directory**

Run: `mkdir -p ~/.pickle-bot/skills/brainstorming`

**Step 2: Create example skill**

Create `~/.pickle-bot/skills/brainstorming/SKILL.md`:

```markdown
---
name: Brainstorming Ideas
description: Turn ideas into fully formed designs through collaborative dialogue
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

## Process

1. **Explore project context** - Check files, docs, recent commits
2. **Ask clarifying questions** - One at a time, understand purpose/constraints/success criteria
3. **Propose 2-3 approaches** - With trade-offs and your recommendation
4. **Present design** - In sections scaled to their complexity, get user approval after each section
5. **Write design doc** - Save to `docs/plans/YYYY-MM-DD-<topic>-design.md` and commit

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design, get approval before moving on
```

**Step 3: Verify skill is discoverable**

Run: `uv run python -c "from picklebot.core.skill_loader import SkillLoader; from pathlib import Path; loader = SkillLoader(Path.home() / '.pickle-bot' / 'skills'); skills = loader.discover_skills(); print([s.name for s in skills])"`

Expected: Output includes "Brainstorming Ideas"

**Step 4: Commit (documentation)**

Since this is a user-specific file, no git commit needed. But document in README.

---

## Task 11: Update Documentation

**Files:**
- Modify: `README.md` (if exists)
- Modify: `CLAUDE.md`

**Step 1: Add skill system to CLAUDE.md**

Add section to `CLAUDE.md`:

```markdown
### Skill System

Skills are user-defined capabilities that can be loaded on-demand by the LLM. Skills are defined in `~/.pickle-bot/skills/[name]/SKILL.md` files with YAML frontmatter.

**Skill Definition Format:**

```markdown
---
name: Skill Display Name
description: Brief description for LLM to decide whether to load
---

# Skill Name

Instructions for the skill...
```

**Enabling Skills:**

Add `allow_skills: true` to your agent's AGENT.md:

```markdown
---
name: My Agent
allow_skills: true
---

You are a helpful assistant...
```

**Available Skills:**

When skills are enabled, the LLM has access to a "skill" tool that presents all available skills and can load their content on demand.
```

**Step 2: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: document skill system usage"
```

---

## Task 12: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run ruff check .`
Expected: No errors (or fix any that appear)

**Step 3: Run type checking**

Run: `uv run mypy .`
Expected: No errors (or fix any that appear)

**Step 4: Format code**

Run: `uv run black .`

**Step 5: Final commit**

```bash
git add .
git commit -m "chore: format and fix linting issues"
```

---

## Summary

This implementation plan adds a complete skill system to pickle-bot:

1. **Skill Models** - Pydantic models for skill definitions
2. **SkillLoader** - Discovers and loads skills from filesystem
3. **AgentDef Update** - Adds `allow_skills` boolean field
4. **Skill Tool** - Factory function creating dynamic tool with skill schema
5. **Agent Integration** - Conditionally registers skill tool based on agent config
6. **Configuration** - Adds skills_path to Config
7. **Documentation** - Updates CLAUDE.md with skill system usage

The skill system follows these key principles:
- **Lazy loading** - Skills loaded on-demand via tool call
- **Graceful degradation** - Invalid skills are skipped with warnings
- **Backwards compatible** - Existing agents continue working normally
- **User-editable** - Skills are markdown files users can modify
- **Dynamic schema** - Tool enum/description built from available skills

All tasks follow TDD: write test, verify failure, implement, verify pass, commit.
