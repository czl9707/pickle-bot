# Simplify API Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove redundant `enabled` field from API config - presence of `api` section enables it.

**Architecture:** Change `Config.api` from required `ApiConfig` to optional `ApiConfig | None`. Server checks `if config.api:` instead of `if config.api.enabled:`. Onboarding sets empty dict when user selects API.

**Tech Stack:** Python, Pydantic, Pytest

---

## Task 1: Update ApiConfig Model

**Files:**
- Modify: `src/picklebot/utils/config.py:54-59`

**Step 1: Remove `enabled` field from ApiConfig**

Change:
```python
class ApiConfig(BaseModel):
    """HTTP API configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, lt=65536)
```

To:
```python
class ApiConfig(BaseModel):
    """HTTP API configuration."""

    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, lt=65536)
```

**Step 2: Make `api` optional in Config class**

Change line 135:
```python
api: ApiConfig = Field(default_factory=ApiConfig)
```

To:
```python
api: ApiConfig | None = None
```

**Step 3: Commit**

```bash
git add src/picklebot/utils/config.py
git commit -m "refactor(config): remove enabled field from ApiConfig, make api optional"
```

---

## Task 2: Update Server API Check

**Files:**
- Modify: `src/picklebot/server/server.py:34-38`

**Step 1: Change enabled check to presence check**

Change:
```python
if self.context.config.api.enabled:
```

To:
```python
if self.context.config.api:
```

**Step 2: Commit**

```bash
git add src/picklebot/server/server.py
git commit -m "refactor(server): check api presence instead of enabled field"
```

---

## Task 3: Update Onboarding Step

**Files:**
- Modify: `src/picklebot/cli/onboarding/steps.py:128-129`

**Step 1: Set empty dict instead of enabled=True**

Change:
```python
if "api" in selected:
    state["api"] = {"enabled": True}
```

To:
```python
if "api" in selected:
    state["api"] = {}
```

**Step 2: Commit**

```bash
git add src/picklebot/cli/onboarding/steps.py
git commit -m "refactor(onboarding): set empty api dict instead of enabled=True"
```

---

## Task 4: Update Documentation

**Files:**
- Modify: `docs/features.md:148-154`
- Modify: `docs/configuration.md:90-94`

**Step 1: Update features.md**

Change:
```yaml
```yaml
api:
  enabled: true
  host: "127.0.0.1"
  port: 8000
```
```

To:
```yaml
```yaml
api:
  host: "127.0.0.1"
  port: 8000
```
```

**Step 2: Update configuration.md**

Change:
```yaml
# HTTP API
api:
  enabled: true
  host: "127.0.0.1"
  port: 8000
```

To:
```yaml
# HTTP API (omit section to disable)
api:
  host: "127.0.0.1"
  port: 8000
```

**Step 3: Commit**

```bash
git add docs/features.md docs/configuration.md
git commit -m "docs: remove enabled field from api config examples"
```

---

## Task 5: Update Tests

**Files:**
- Modify: `tests/utils/test_config.py:252-262`
- Modify: `tests/server/test_server.py:76`
- Modify: `tests/cli/onboarding/test_steps.py:261`

**Step 1: Update test_config.py**

Change:
```python
def test_config_has_api_config(self, llm_config):
    """Config should include api configuration."""
    config = Config(
        workspace=Path("/tmp/test-workspace"),
        llm=llm_config,
        default_agent="pickle",
        api=ApiConfig(enabled=True, host="0.0.0.0", port=3000),
    )
    assert config.api.enabled is True
    assert config.api.host == "0.0.0.0"
    assert config.api.port == 3000
```

To:
```python
def test_config_has_api_config(self, llm_config):
    """Config should include api configuration when provided."""
    config = Config(
        workspace=Path("/tmp/test-workspace"),
        llm=llm_config,
        default_agent="pickle",
        api=ApiConfig(host="0.0.0.0", port=3000),
    )
    assert config.api is not None
    assert config.api.host == "0.0.0.0"
    assert config.api.port == 3000

def test_config_api_defaults_to_none(self, llm_config):
    """Config should have api=None by default."""
    config = Config(
        workspace=Path("/tmp/test-workspace"),
        llm=llm_config,
        default_agent="pickle",
    )
    assert config.api is None
```

**Step 2: Update test_server.py**

Change:
```python
context.config.api.enabled = False
```

To:
```python
context.config.api = None
```

**Step 3: Update test_steps.py**

Change:
```python
assert state["api"] == {"enabled": True}
```

To:
```python
assert state["api"] == {}
```

**Step 4: Run tests**

```bash
uv run pytest tests/utils/test_config.py tests/server/test_server.py tests/cli/onboarding/test_steps.py -v
```

Expected: All tests pass

**Step 5: Commit**

```bash
git add tests/utils/test_config.py tests/server/test_server.py tests/cli/onboarding/test_steps.py
git commit -m "test: update tests for simplified api config"
```

---

## Task 6: Final Verification

**Step 1: Run full test suite**

```bash
uv run pytest
```

Expected: All tests pass

**Step 2: Run linting**

```bash
uv run black . && uv run ruff check .
```

Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: any remaining issues"
```
