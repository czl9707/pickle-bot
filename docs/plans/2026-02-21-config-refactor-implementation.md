# Config System Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate user preferences from runtime state with two-file config model.

**Architecture:** Three-layer merge (Pydantic defaults ← config.user.yaml ← config.runtime.yaml) with `set_user()` and `set_runtime()` methods for writing.

**Tech Stack:** Python, Pydantic, YAML

---

### Task 1: Add config file path constants and runtime loading

**Files:**
- Modify: `src/picklebot/utils/config.py`

**Step 1: Write the failing test**

Create `tests/utils/test_config_files.py`:

```python
"""Tests for config file handling."""

import pytest
import yaml
from pathlib import Path
from picklebot.utils.config import Config


class TestConfigFiles:
    """Tests for config file paths and loading."""

    def test_loads_runtime_config(self, tmp_path):
        """Runtime config is merged on top of user config."""
        # Create minimal system config
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        # Create user config
        user_config = tmp_path / "config.user.yaml"
        user_config.write_text("default_agent: user-agent\n")

        # Create runtime config
        runtime_config = tmp_path / "config.runtime.yaml"
        runtime_config.write_text("default_agent: runtime-agent\n")

        config = Config.load(tmp_path)

        # Runtime should win
        assert config.default_agent == "runtime-agent"

    def test_runtime_config_optional(self, tmp_path):
        """Config loads fine without runtime config."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        config = Config.load(tmp_path)
        assert config.default_agent == "system-agent"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config_files.py -v`
Expected: FAIL - runtime config not loaded

**Step 3: Add runtime config loading**

Modify `src/picklebot/utils/config.py`, update the `load()` method:

```python
@classmethod
def load(cls, workspace_dir: Path) -> "Config":
    """Load configuration from ~/.pickle-bot/."""
    config_data: dict = {"workspace": workspace_dir}

    system_config = workspace_dir / "config.system.yaml"
    user_config = workspace_dir / "config.user.yaml"
    runtime_config = workspace_dir / "config.runtime.yaml"

    # Load system config (defaults)
    if system_config.exists():
        with open(system_config) as f:
            system_data = yaml.safe_load(f) or {}
        config_data.update(system_data)

    # Deep merge user config (overrides system)
    if user_config.exists():
        with open(user_config) as f:
            user_data = yaml.safe_load(f) or {}
        config_data = cls._deep_merge(config_data, user_data)

    # Deep merge runtime config (overrides user)
    if runtime_config.exists():
        with open(runtime_config) as f:
            runtime_data = yaml.safe_load(f) or {}
        config_data = cls._deep_merge(config_data, runtime_data)

    return cls.model_validate(config_data)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config_files.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config_files.py
git commit -m "feat(config): add runtime config loading"
```

---

### Task 2: Add `set_user()` method

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `tests/utils/test_config_files.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config_files.py`:

```python
class TestConfigSetters:
    """Tests for config setter methods."""

    def test_set_user_creates_file(self, tmp_path):
        """set_user creates config.user.yaml if it doesn't exist."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # File should exist
        user_config = tmp_path / "config.user.yaml"
        assert user_config.exists()

        # Content should be correct
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"

    def test_set_user_preserves_existing(self, tmp_path):
        """set_user preserves other fields in config.user.yaml."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        user_config = tmp_path / "config.user.yaml"
        user_config.write_text("chat_max_history: 100\n")

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # Both fields should be present
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"
        assert data["chat_max_history"] == 100

    def test_set_user_updates_in_memory(self, tmp_path):
        """set_user updates the in-memory config object."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        assert config.default_agent == "my-agent"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config_files.py::TestConfigSetters -v`
Expected: FAIL - `set_user` not defined

**Step 3: Add `set_user()` method**

Add to `src/picklebot/utils/config.py` in the `Config` class:

```python
def set_user(self, key: str, value: Any) -> None:
    """
    Update a config value in config.user.yaml.

    Args:
        key: Config key to update
        value: New value
    """
    user_config_path = self.workspace / "config.user.yaml"

    # Load existing or start fresh
    if user_config_path.exists():
        with open(user_config_path) as f:
            user_data = yaml.safe_load(f) or {}
    else:
        user_data = {}

    # Update the key
    user_data[key] = value

    # Write back
    with open(user_config_path, "w") as f:
        yaml.dump(user_data, f)

    # Update in-memory config
    setattr(self, key, value)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config_files.py::TestConfigSetters -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config_files.py
git commit -m "feat(config): add set_user method"
```

---

### Task 3: Add `set_runtime()` method

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `tests/utils/test_config_files.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config_files.py` in `TestConfigSetters`:

```python
    def test_set_runtime_creates_file(self, tmp_path):
        """set_runtime creates config.runtime.yaml if it doesn't exist."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        config = Config.load(tmp_path)
        config.set_runtime("default_agent", "runtime-agent")

        # File should exist
        runtime_config = tmp_path / "config.runtime.yaml"
        assert runtime_config.exists()

        # Content should be correct
        data = yaml.safe_load(runtime_config.read_text())
        assert data["default_agent"] == "runtime-agent"

    def test_set_runtime_updates_in_memory(self, tmp_path):
        """set_runtime updates the in-memory config object."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text("default_agent: system-agent\n")

        config = Config.load(tmp_path)
        config.set_runtime("default_agent", "runtime-agent")

        assert config.default_agent == "runtime-agent"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config_files.py::TestConfigSetters::test_set_runtime -v`
Expected: FAIL - `set_runtime` not defined

**Step 3: Add `set_runtime()` method**

Add to `src/picklebot/utils/config.py` in the `Config` class:

```python
def set_runtime(self, key: str, value: Any) -> None:
    """
    Update a runtime value in config.runtime.yaml.

    Args:
        key: Config key to update
        value: New value
    """
    runtime_config_path = self.workspace / "config.runtime.yaml"

    # Load existing or start fresh
    if runtime_config_path.exists():
        with open(runtime_config_path) as f:
            runtime_data = yaml.safe_load(f) or {}
    else:
        runtime_data = {}

    # Update the key
    runtime_data[key] = value

    # Write back
    with open(runtime_config_path, "w") as f:
        yaml.dump(runtime_data, f)

    # Update in-memory config
    setattr(self, key, value)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config_files.py::TestConfigSetters::test_set_runtime -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config_files.py
git commit -m "feat(config): add set_runtime method"
```

---

### Task 4: Update API router to use `set_user()`

**Files:**
- Modify: `src/picklebot/api/routers/config.py`

**Step 1: Run existing tests**

Run: `uv run pytest tests/api/test_config.py -v`
Expected: PASS (current behavior)

**Step 2: Refactor to use `set_user()`**

Modify `src/picklebot/api/routers/config.py`:

```python
"""Config resource router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.api.schemas import ConfigUpdate
from picklebot.core.context import SharedContext

router = APIRouter()


class ConfigResponse(BaseModel):
    """Response model for config (excludes sensitive fields)."""

    default_agent: str
    chat_max_history: int
    job_max_history: int


@router.get("", response_model=ConfigResponse)
def get_config(ctx: SharedContext = Depends(get_context)) -> dict:
    """Get current config."""
    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
    }


@router.patch("", response_model=ConfigResponse)
def update_config(
    data: ConfigUpdate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Update config fields."""
    if data.default_agent is not None:
        ctx.config.set_user("default_agent", data.default_agent)
    if data.chat_max_history is not None:
        ctx.config.set_user("chat_max_history", data.chat_max_history)
    if data.job_max_history is not None:
        ctx.config.set_user("job_max_history", data.job_max_history)

    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
    }
```

**Step 3: Run tests to verify behavior unchanged**

Run: `uv run pytest tests/api/test_config.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/api/routers/config.py
git commit -m "refactor(api): use set_user for config updates"
```

---

### Task 5: Update existing tests for new behavior

**Files:**
- Modify: `tests/tools/test_post_message_tool.py`

**Step 1: Check current test setup**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: May have issues if test assumes `config.system.yaml` is required

**Step 2: Review and fix if needed**

The test at line 21 creates `config.system.yaml`. This should still work since we still load it. Run tests to confirm.

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: PASS

**Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All PASS

**Step 4: Commit (if changes needed)**

```bash
git add tests/
git commit -m "test: update tests for config refactor"
```

---

### Task 6: Update docs and CLAUDE.md

**Files:**
- Modify: `docs/configuration.md`
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md**

Update the "Config Loading" section in `CLAUDE.md`:

```markdown
### Config Loading

Three-layer merge: `Pydantic defaults` <- `config.user.yaml` <- `config.runtime.yaml`

- `config.user.yaml` - User preferences (edited via API or manually)
- `config.runtime.yaml` - Runtime state (internal only, managed by application)

Use `set_user()` and `set_runtime()` methods to update config:

```python
ctx.config.set_user("default_agent", "cookie")
ctx.config.set_runtime("current_session_id", "abc123")
```
```

**Step 2: Update docs/configuration.md**

Update to reflect new file structure (if this file exists and documents config files).

**Step 3: Commit**

```bash
git add CLAUDE.md docs/configuration.md
git commit -m "docs: update config documentation for refactor"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add runtime config loading |
| 2 | Add `set_user()` method |
| 3 | Add `set_runtime()` method |
| 4 | Refactor API router to use `set_user()` |
| 5 | Fix/update existing tests |
| 6 | Update documentation |
