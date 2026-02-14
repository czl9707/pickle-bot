# Resolve Config Paths Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Flatten logging/history config and resolve paths to absolute during config loading.

**Architecture:** Remove single-field `LoggingConfig` and `HistoryConfig` wrapper classes. Add `logging_path` and `history_path` directly to `Config` as `Path` types. Use Pydantic model validator to reject absolute paths and resolve relative paths against workspace.

**Tech Stack:** Pydantic v2 model_validator, pathlib

---

## Task 1: Add Tests for Config Path Resolution

**Files:**
- Create: `tests/utils/test_config.py`

**Step 1: Create test file with failing tests**

```python
"""Tests for config path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def minimal_llm_config():
    """Minimal LLM config for testing."""
    return LLMConfig(
        provider="test",
        model="test-model",
        api_key="test-key",
    )


class TestPathResolution:
    def test_resolves_relative_logging_path(self, minimal_llm_config):
        """Relative logging_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            logging_path=Path(".logs"),
        )
        assert config.logging_path == Path("/workspace/.logs")

    def test_resolves_relative_history_path(self, minimal_llm_config):
        """Relative history_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            history_path=Path(".history"),
        )
        assert config.history_path == Path("/workspace/.history")

    def test_uses_default_paths(self, minimal_llm_config):
        """Default paths should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
        )
        assert config.logging_path == Path("/workspace/.logs")
        assert config.history_path == Path("/workspace/.history")


class TestRejectsAbsolutePaths:
    def test_rejects_absolute_logging_path(self, minimal_llm_config):
        """Absolute logging_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                logging_path=Path("/var/log"),
            )
        assert "logging_path must be relative" in str(exc.value)

    def test_rejects_absolute_history_path(self, minimal_llm_config):
        """Absolute history_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                history_path=Path("/var/history"),
            )
        assert "history_path must be relative" in str(exc.value)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: FAIL (tests will fail because `logging_path`/`history_path` don't exist yet)

**Step 3: Commit**

```bash
git add tests/utils/test_config.py
git commit -m "test: add tests for config path resolution"
```

---

## Task 2: Update Config Model

**Files:**
- Modify: `src/picklebot/utils/config.py`

**Step 1: Remove LoggingConfig and HistoryConfig classes**

Delete lines 53-62 (the `LoggingConfig` and `HistoryConfig` classes).

**Step 2: Update imports**

Add `model_validator` to the pydantic import:

```python
from pydantic import BaseModel, Field, field_validator, model_validator
```

**Step 3: Update Config class**

Replace the `logging` and `history` fields with `logging_path` and `history_path`, and add the model validator:

```python
class Config(BaseModel):
    """
    Main configuration for pickle-bot.

    Configuration is loaded from ~/.pickle-bot/:
    1. config.system.yaml - System defaults (shipped with the app)
    2. config.user.yaml - User overrides (optional, overrides system)

    User config takes precedence over system config.
    """

    workspace: Path
    llm: LLMConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    logging_path: Path = Field(default=Path(".logs"))
    history_path: Path = Field(default=Path(".history"))

    @model_validator(mode="after")
    def resolve_paths(self) -> "Config":
        """Resolve relative paths to absolute using workspace."""
        for field_name in ("logging_path", "history_path"):
            path = getattr(self, field_name)
            if path.is_absolute():
                raise ValueError(f"{field_name} must be relative, got: {path}")
            setattr(self, field_name, self.workspace / path)
        return self
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py
git commit -m "refactor(config): flatten logging/history into path fields"
```

---

## Task 3: Update Logging Usage

**Files:**
- Modify: `src/picklebot/utils/logging.py`

**Step 1: Simplify path access**

Change line 20 from:
```python
file_handler = logging.FileHandler(config.workspace.joinpath(config.logging.path))
```

To:
```python
file_handler = logging.FileHandler(config.logging_path)
```

**Step 2: Run tests to verify nothing is broken**

Run: `uv run pytest -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/utils/logging.py
git commit -m "refactor(logging): use resolved logging_path from config"
```

---

## Task 4: Update History Usage

**Files:**
- Modify: `src/picklebot/core/history.py`

**Step 1: Simplify from_config method**

Change line 51 from:
```python
return HistoryStore(config.workspace / config.history.path)
```

To:
```python
return HistoryStore(config.history_path)
```

**Step 2: Run tests to verify nothing is broken**

Run: `uv run pytest -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/history.py
git commit -m "refactor(history): use resolved history_path from config"
```

---

## Task 5: Run Full Test Suite and Lint

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linters**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address lint issues from config refactor"
```
