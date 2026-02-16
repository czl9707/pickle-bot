# Definition Loader Utilities Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract shared markdown parsing and discovery logic from three loaders into a common utility module.

**Architecture:** Create `utils/def_loader.py` with `parse_frontmatter()`, `discover_definitions()`, and generic error classes. Refactor all three loaders to use these utilities while maintaining their public API.

**Tech Stack:** Python 3.13, Pydantic, PyYAML, pytest

---

## Task 1: Create `parse_frontmatter()` utility with tests

**Files:**
- Create: `src/picklebot/utils/def_loader.py`
- Create: `tests/utils/test_def_loader.py`

**Step 1: Write the failing test for basic parsing**

Create `tests/utils/test_def_loader.py`:

```python
"""Tests for definition loader utilities."""

import pytest

from picklebot.utils.def_loader import parse_frontmatter


class TestParseFrontmatter:
    def test_parse_basic_frontmatter(self):
        """Parse simple YAML frontmatter and body."""
        content = "---\nname: Test\n---\nBody content here."
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == "Body content here."

    def test_parse_with_multiple_fields(self):
        """Parse frontmatter with multiple YAML fields."""
        content = "---\nname: Test\nversion: 1.0\nenabled: true\n---\nBody"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test", "version": 1.0, "enabled": True}
        assert body == "Body"

    def test_parse_preserves_delimiter_in_body(self):
        """Preserve --- delimiters that appear in body."""
        content = "---\nname: Test\n---\nHere is --- a separator\n---\nmore content"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == "Here is --- a separator\n---\nmore content"

    def test_parse_empty_frontmatter(self):
        """Handle empty frontmatter."""
        content = "---\n---\nBody content"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Body content"

    def test_parse_no_frontmatter_returns_empty_dict(self):
        """Return empty dict and full content when no frontmatter."""
        content = "Just body content\nno frontmatter"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Just body content\nno frontmatter"

    def test_parse_empty_body(self):
        """Handle empty body after frontmatter."""
        content = "---\nname: Test\n---\n"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == ""
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_def_loader.py -v`
Expected: FAIL with "cannot import name 'parse_frontmatter'"

**Step 3: Create `def_loader.py` with `parse_frontmatter()`**

Create `src/picklebot/utils/def_loader.py`:

```python
"""Shared utilities for loading definition files (agents, skills, crons)."""

from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter + markdown body.

    Args:
        content: Raw file content

    Returns:
        Tuple of (frontmatter dict, body string)
    """
    parts = [p for p in content.split("---\n") if p.strip()]

    if len(parts) < 2:
        return {}, content

    frontmatter_text = parts[0]
    body = "---\n".join(parts[1:])

    frontmatter = yaml.safe_load(frontmatter_text) or {}
    return frontmatter, body
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_def_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/def_loader.py tests/utils/test_def_loader.py
git commit -m "feat: add parse_frontmatter utility"
```

---

## Task 2: Add error classes with tests

**Files:**
- Modify: `src/picklebot/utils/def_loader.py`
- Modify: `tests/utils/test_def_loader.py`

**Step 1: Write the failing tests for error classes**

Add to `tests/utils/test_def_loader.py`:

```python
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError


class TestDefNotFoundError:
    def test_error_message_format(self):
        """Error message uses capitalized kind."""
        error = DefNotFoundError("agent", "my-agent")

        assert str(error) == "Agent not found: my-agent"
        assert error.kind == "agent"
        assert error.def_id == "my-agent"

    def test_error_message_with_cron_kind(self):
        """Error message works with cron kind."""
        error = DefNotFoundError("cron", "daily-task")

        assert str(error) == "Cron not found: daily-task"


class TestInvalidDefError:
    def test_error_message_format(self):
        """Error message includes reason."""
        error = InvalidDefError("skill", "my-skill", "missing required field: name")

        assert str(error) == "Invalid skill 'my-skill': missing required field: name"
        assert error.kind == "skill"
        assert error.def_id == "my-skill"
        assert error.reason == "missing required field: name"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_def_loader.py -v`
Expected: FAIL with "cannot import name 'DefNotFoundError'"

**Step 3: Add error classes to `def_loader.py`**

Add to `src/picklebot/utils/def_loader.py`:

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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_def_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/def_loader.py tests/utils/test_def_loader.py
git commit -m "feat: add DefNotFoundError and InvalidDefError classes"
```

---

## Task 3: Add `discover_definitions()` utility with tests

**Files:**
- Modify: `src/picklebot/utils/def_loader.py`
- Modify: `tests/utils/test_def_loader.py`

**Step 1: Write the failing tests for discovery**

Add to `tests/utils/test_def_loader.py`:

```python
import logging
from pathlib import Path
import tempfile

from picklebot.utils.def_loader import discover_definitions


class TestDiscoverDefinitions:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self):
        return logging.getLogger("test")

    def test_discovers_valid_definitions(self, temp_dir, logger):
        """Discover definitions from valid files."""
        # Create skill1/SKILL.md
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent 1")

        # Create skill2/SKILL.md
        skill2 = temp_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("---\nname: Skill Two\n---\nContent 2")

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill, logger)

        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Skill One", "Skill Two"}

    def test_skips_directories_without_definition_file(self, temp_dir, logger):
        """Skip directories that don't have the definition file."""
        # Valid definition
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        # Directory without SKILL.md
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill, logger)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"

    def test_skips_invalid_definitions_via_callback_returning_none(self, temp_dir, logger):
        """Skip definitions when parse callback returns None."""
        # Valid definition
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        # Invalid definition (missing name)
        skill2 = temp_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("---\n---\nContent")

        def parse_skill(def_id, fm, body):
            if "name" not in fm:
                return None
            return {"id": def_id, "name": fm["name"]}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill, logger)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"

    def test_returns_empty_list_for_nonexistent_path(self, temp_dir, logger):
        """Return empty list when path doesn't exist."""
        nonexistent = temp_dir / "nonexistent"

        def parse(def_id, fm, body):
            return {"id": def_id}

        results = discover_definitions(nonexistent, "SKILL.md", parse, logger)

        assert results == []

    def test_ignores_files_in_root_directory(self, temp_dir, logger):
        """Only process subdirectories, not files in root."""
        # File in root (should be ignored)
        (temp_dir / "SKILL.md").write_text("---\nname: Root\n---\nContent")

        # Valid definition in subdirectory
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill, logger)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_def_loader.py::TestDiscoverDefinitions -v`
Expected: FAIL with "cannot import name 'discover_definitions'"

**Step 3: Add `discover_definitions()` to `def_loader.py`**

Add to `src/picklebot/utils/def_loader.py`:

```python
import logging
from typing import Callable, TypeVar

T = TypeVar("T")


def discover_definitions(
    path: Path,
    filename: str,
    parse_metadata: Callable[[str, dict[str, Any], str], T | None],
    logger: logging.Logger,
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
    """
    if not path.exists():
        logger.warning(f"Definitions directory not found: {path}")
        return []

    results = []
    for def_dir in path.iterdir():
        if not def_dir.is_dir():
            continue

        def_file = def_dir / filename
        if not def_file.exists():
            logger.warning(f"No {filename} found in {def_dir.name}")
            continue

        try:
            content = def_file.read_text()
            frontmatter, body = parse_frontmatter(content)
            metadata = parse_metadata(def_dir.name, frontmatter, body)
            if metadata is not None:
                results.append(metadata)
        except Exception as e:
            logger.warning(f"Failed to parse {def_dir.name}: {e}")
            continue

    return results
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_def_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/def_loader.py tests/utils/test_def_loader.py
git commit -m "feat: add discover_definitions utility"
```

---

## Task 4: Update `utils/__init__.py` to export new utilities

**Files:**
- Modify: `src/picklebot/utils/__init__.py`

**Step 1: Update exports**

Modify `src/picklebot/utils/__init__.py`:

```python
"""Utilities package."""

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_frontmatter,
)
from picklebot.utils.logging import setup_logging

__all__ = [
    "DefNotFoundError",
    "InvalidDefError",
    "discover_definitions",
    "parse_frontmatter",
    "setup_logging",
]
```

**Step 2: Verify import works**

Run: `uv run python -c "from picklebot.utils import parse_frontmatter, discover_definitions, DefNotFoundError, InvalidDefError; print('OK')"`
Expected: Output "OK"

**Step 3: Commit**

```bash
git add src/picklebot/utils/__init__.py
git commit -m "feat: export def_loader utilities from utils package"
```

---

## Task 5: Refactor `AgentLoader` to use utilities

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Update test imports to use new error classes**

Modify `tests/core/test_agent_loader.py`:

Change imports from:
```python
from picklebot.core.agent_loader import (
    AgentLoader,
    AgentNotFoundError,
    InvalidAgentError,
)
```

To:
```python
from picklebot.core.agent_loader import AgentLoader
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError
```

Update test assertions to use new error classes:
- `AgentNotFoundError` → `DefNotFoundError`
- `InvalidAgentError` → `InvalidDefError`
- `exc.value.agent_id` → `exc.value.def_id`
- `exc.value.reason` stays the same

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: FAIL (import errors, attribute errors)

**Step 3: Refactor `AgentLoader` to use utilities**

Modify `src/picklebot/core/agent_loader.py`:

```python
"""Agent definition loader."""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from picklebot.utils.config import Config, LLMConfig
from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    parse_frontmatter,
)


class AgentBehaviorConfig(BaseModel):
    """Agent behavior settings."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)


class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    system_prompt: str
    llm: LLMConfig
    behavior: AgentBehaviorConfig
    allow_skills: bool = False


# Keep old error names as aliases for backwards compatibility
AgentNotFoundError = DefNotFoundError
InvalidAgentError = InvalidDefError


class AgentLoader:
    """Loads agent definitions from AGENT.md files."""

    @staticmethod
    def from_config(config: Config) -> "AgentLoader":
        return AgentLoader(config.agents_path, config.llm)

    def __init__(self, agents_path: Path, shared_llm: LLMConfig):
        """
        Initialize AgentLoader.

        Args:
            agents_path: Directory containing agent folders
            shared_llm: Shared LLM config to fall back to
        """
        self.agents_path = agents_path
        self.shared_llm = shared_llm

    def load(self, agent_id: str) -> AgentDef:
        """
        Load agent by ID.

        Args:
            agent_id: Agent folder name

        Returns:
            AgentDef with merged settings

        Raises:
            DefNotFoundError: Agent folder or file doesn't exist
            InvalidDefError: Agent file is malformed
        """
        agent_file = self.agents_path / agent_id / "AGENT.md"
        if not agent_file.exists():
            raise DefNotFoundError("agent", agent_id)

        try:
            content = agent_file.read_text()
            frontmatter, body = parse_frontmatter(content)
        except Exception as e:
            raise InvalidDefError("agent", agent_id, str(e))

        if "name" not in frontmatter:
            raise InvalidDefError("agent", agent_id, "missing required field: name")

        merged_llm = self._merge_llm_config(frontmatter)

        return AgentDef(
            id=agent_id,
            name=frontmatter["name"],
            system_prompt=body.strip(),
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
            allow_skills=frontmatter.get("allow_skills", False),
        )

    def _merge_llm_config(self, frontmatter: dict[str, Any]) -> LLMConfig:
        """
        Merge agent overrides with shared LLM config.

        Args:
            frontmatter: Parsed frontmatter dict

        Returns:
            LLMConfig with merged settings
        """
        return LLMConfig(
            provider=frontmatter.get("provider", self.shared_llm.provider),
            model=frontmatter.get("model", self.shared_llm.model),
            api_key=frontmatter.get("api_key", self.shared_llm.api_key),
            api_base=frontmatter.get("api_base", self.shared_llm.api_base),
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "refactor: AgentLoader uses def_loader utilities"
```

---

## Task 6: Refactor `SkillLoader` to use utilities

**Files:**
- Modify: `src/picklebot/core/skill_loader.py`
- Modify: `tests/core/test_skill_loader.py`

**Step 1: Read existing skill loader tests**

Run: `cat tests/core/test_skill_loader.py`

Review the test structure and update imports accordingly.

**Step 2: Update test imports to use new error classes**

Modify `tests/core/test_skill_loader.py` to import errors from `def_loader`:

```python
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError
```

Update test assertions:
- `SkillNotFoundError` → `DefNotFoundError`
- `exc.value.skill_id` → `exc.value.def_id` (if applicable)

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_skill_loader.py -v`
Expected: FAIL

**Step 4: Refactor `SkillLoader` to use utilities**

Modify `src/picklebot/core/skill_loader.py`:

```python
"""Skill loader for discovering and loading skills."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from picklebot.utils.config import Config

logger = logging.getLogger(__name__)


class SkillMetadata(BaseModel):
    """Lightweight skill info for discovery."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str


class SkillDef(BaseModel):
    """Loaded skill definition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    content: str


# Keep old error name as alias for backwards compatibility
SkillNotFoundError = DefNotFoundError


class SkillLoader:
    """Load and manage skill definitions from filesystem."""

    @staticmethod
    def from_config(config: "Config") -> "SkillLoader":
        """Create SkillLoader from config."""
        return SkillLoader(config.skills_path)

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path

    def discover_skills(self) -> list[SkillMetadata]:
        """Scan skills directory and return list of valid SkillMetadata."""
        return discover_definitions(
            self.skills_path,
            "SKILL.md",
            self._parse_skill_metadata,
            logger,
        )

    def _parse_skill_metadata(
        self, skill_id: str, frontmatter: dict, body: str
    ) -> SkillMetadata | None:
        """Parse skill metadata from frontmatter."""
        if "name" not in frontmatter or "description" not in frontmatter:
            logger.warning(f"Missing required fields in skill {skill_id}")
            return None

        return SkillMetadata(
            id=skill_id,
            name=frontmatter["name"],
            description=frontmatter["description"],
        )

    def load_skill(self, skill_id: str) -> SkillDef:
        """Load full skill definition by ID.

        Args:
            skill_id: The skill directory name

        Returns:
            SkillDef with full content

        Raises:
            DefNotFoundError: If skill doesn't exist or is invalid
        """
        skill_dir = self.skills_path / skill_id
        if not skill_dir.exists() or not skill_dir.is_dir():
            raise DefNotFoundError("skill", skill_id)

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise DefNotFoundError("skill", skill_id)

        try:
            content = skill_file.read_text()
            frontmatter, body = parse_frontmatter(content)

            if "name" not in frontmatter or "description" not in frontmatter:
                raise InvalidDefError(
                    "skill", skill_id, "missing required fields: name, description"
                )

            return SkillDef(
                id=skill_id,
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=body.strip(),
            )
        except DefNotFoundError:
            raise
        except InvalidDefError:
            raise
        except Exception as e:
            raise DefNotFoundError("skill", skill_id)
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_skill_loader.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/skill_loader.py tests/core/test_skill_loader.py
git commit -m "refactor: SkillLoader uses def_loader utilities"
```

---

## Task 7: Refactor `CronLoader` to use utilities

**Files:**
- Modify: `src/picklebot/core/cron_loader.py`
- Modify: `tests/core/test_cron_loader.py`

**Step 1: Read existing cron loader tests**

Run: `cat tests/core/test_cron_loader.py`

Review the test structure and update imports accordingly.

**Step 2: Update test imports to use new error classes**

Modify `tests/core/test_cron_loader.py` to import errors from `def_loader`:

```python
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError
```

Update test assertions:
- `CronNotFoundError` → `DefNotFoundError`
- `InvalidCronError` → `InvalidDefError`
- `exc.value.cron_id` → `exc.value.def_id`

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_cron_loader.py -v`
Expected: FAIL

**Step 4: Refactor `CronLoader` to use utilities**

Modify `src/picklebot/core/cron_loader.py`:

```python
"""Cron job definition loader."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from datetime import datetime

from croniter import croniter
from pydantic import BaseModel, field_validator

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from picklebot.utils.config import Config

logger = logging.getLogger(__name__)


class CronMetadata(BaseModel):
    """Lightweight cron info for discovery."""

    id: str
    name: str
    agent: str
    schedule: str


class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    agent: str
    schedule: str
    prompt: str

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: str) -> str:
        """Validate cron expression and enforce 5-minute minimum granularity."""
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")

        base = datetime(2024, 1, 1, 0, 0)
        cron = croniter(v, base)
        first_run = cron.get_next(datetime)
        second_run = cron.get_next(datetime)
        gap_minutes = (second_run - first_run).total_seconds() / 60

        if gap_minutes < 5:
            raise ValueError(
                f"Schedule must have minimum 5-minute granularity. Got: {v} (runs every {gap_minutes:.0f} min)"
            )

        return v


# Keep old error names as aliases for backwards compatibility
CronNotFoundError = DefNotFoundError
InvalidCronError = InvalidDefError


class CronLoader:
    """Loads cron job definitions from CRON.md files."""

    @staticmethod
    def from_config(config: "Config") -> "CronLoader":
        """Create CronLoader from config."""
        return CronLoader(config.crons_path)

    def __init__(self, crons_path: Path):
        """
        Initialize CronLoader.

        Args:
            crons_path: Directory containing cron folders
        """
        self.crons_path = crons_path

    def discover_crons(self) -> list[CronMetadata]:
        """
        Scan crons directory, return lightweight metadata for all valid jobs.

        Returns:
            List of CronMetadata for valid cron jobs.
        """
        return discover_definitions(
            self.crons_path,
            "CRON.md",
            self._parse_cron_metadata,
            logger,
        )

    def _parse_cron_metadata(
        self, cron_id: str, frontmatter: dict, body: str
    ) -> CronMetadata | None:
        """Parse cron metadata from frontmatter."""
        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                logger.warning(f"Missing required field '{field}' in cron {cron_id}")
                return None

        try:
            CronDef.validate_schedule(frontmatter["schedule"])
        except ValueError as e:
            logger.warning(f"Invalid schedule in cron {cron_id}: {e}")
            return None

        return CronMetadata(
            id=cron_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
        )

    def load(self, cron_id: str) -> CronDef:
        """
        Load cron by ID.

        Args:
            cron_id: Cron folder name

        Returns:
            CronDef with full definition

        Raises:
            DefNotFoundError: Cron folder or file doesn't exist
            InvalidDefError: Cron file is malformed
        """
        cron_file = self.crons_path / cron_id / "CRON.md"
        if not cron_file.exists():
            raise DefNotFoundError("cron", cron_id)

        try:
            content = cron_file.read_text()
            frontmatter, body = parse_frontmatter(content)
        except Exception as e:
            raise InvalidDefError("cron", cron_id, str(e))

        for field in ["name", "agent", "schedule"]:
            if field not in frontmatter:
                raise InvalidDefError("cron", cron_id, f"missing required field: {field}")

        try:
            CronDef.validate_schedule(frontmatter["schedule"])
        except ValueError as e:
            raise InvalidDefError("cron", cron_id, str(e))

        return CronDef(
            id=cron_id,
            name=frontmatter["name"],
            agent=frontmatter["agent"],
            schedule=frontmatter["schedule"],
            prompt=body.strip(),
        )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_cron_loader.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/cron_loader.py tests/core/test_cron_loader.py
git commit -m "refactor: CronLoader uses def_loader utilities"
```

---

## Task 8: Run full test suite and fix any issues

**Files:**
- Various (if fixes needed)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run ruff check src/`
Expected: No errors

**Step 3: Run type checking**

Run: `uv run mypy src/`
Expected: No errors

**Step 4: Fix any issues if needed**

If any tests fail or linting errors occur, fix them and commit.

**Step 5: Final commit (if fixes were made)**

```bash
git add -A
git commit -m "fix: resolve test/lint issues after def_loader refactor"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Create `parse_frontmatter()` with tests |
| 2 | Add `DefNotFoundError` and `InvalidDefError` classes |
| 3 | Add `discover_definitions()` with tests |
| 4 | Export utilities from `utils/__init__.py` |
| 5 | Refactor `AgentLoader` |
| 6 | Refactor `SkillLoader` |
| 7 | Refactor `CronLoader` |
| 8 | Run full test suite and fix issues |
