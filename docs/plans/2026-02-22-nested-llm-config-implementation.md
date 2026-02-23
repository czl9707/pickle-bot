# Nested LLM Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor agent definitions to use nested `llm:` configuration block, merging temperature/max_tokens into LLMConfig.

**Architecture:** Add temperature/max_tokens fields to LLMConfig with defaults, remove AgentBehaviorConfig class, update parsing to expect nested frontmatter format with deep merge of agent overrides onto global config.

**Tech Stack:** Python, Pydantic, Pytest

---

## Task 1: Update LLMConfig with temperature and max_tokens

**Files:**
- Modify: `src/picklebot/utils/config.py:15-28`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add test to verify LLMConfig has temperature and max_tokens with defaults:

```python
def test_llm_config_has_behavior_defaults():
    """LLMConfig should have temperature and max_tokens with defaults."""
    from picklebot.utils.config import LLMConfig

    config = LLMConfig(
        provider="openai",
        model="gpt-4",
        api_key="test-key",
    )

    assert config.temperature == 0.7
    assert config.max_tokens == 2048
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::test_llm_config_has_behavior_defaults -v`
Expected: FAIL with "LLMConfig has no field 'temperature'"

**Step 3: Add fields to LLMConfig**

In `src/picklebot/utils/config.py`, update `LLMConfig`:

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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::test_llm_config_has_behavior_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add temperature and max_tokens to LLMConfig"
```

---

## Task 2: Remove AgentBehaviorConfig and update AgentDef

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:18-34`

**Step 1: Remove AgentBehaviorConfig class**

Delete the `AgentBehaviorConfig` class (lines 18-22):

```python
# DELETE THIS ENTIRE CLASS:
class AgentBehaviorConfig(BaseModel):
    """Agent behavior settings."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
```

**Step 2: Update AgentDef to remove behavior field**

Update `AgentDef` class:

```python
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    description: str = ""  # Brief description for dispatch tool
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False
```

**Step 3: Run tests to verify changes**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: Some failures due to `behavior` attribute access

**Step 4: Commit**

```bash
git add src/picklebot/core/agent_loader.py
git commit -m "refactor(agent): remove AgentBehaviorConfig, simplify AgentDef"
```

---

## Task 3: Update _parse_agent_def for nested llm format

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:91-114`

**Step 1: Update _parse_agent_def method**

Replace the method:

```python
def _parse_agent_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> AgentDef:
    """Parse agent definition from frontmatter (callback for parse_definition)."""
    # Substitute template variables in body
    body = substitute_template(body, get_template_variables(self.config))

    # Extract nested llm config (optional)
    llm_overrides = frontmatter.get("llm")
    merged_llm = self._merge_llm_config(llm_overrides)

    try:
        return AgentDef(
            id=def_id,
            name=frontmatter["name"],
            description=frontmatter.get("description", ""),
            system_prompt=body.strip(),
            llm=merged_llm,
            allow_skills=frontmatter.get("allow_skills", False),
        )
    except ValidationError as e:
        raise InvalidDefError("agent", def_id, str(e))
```

**Step 2: Run tests**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: Failures persist (merge logic not updated yet)

**Step 3: Commit**

```bash
git add src/picklebot/core/agent_loader.py
git commit -m "refactor(agent): update _parse_agent_def for nested llm format"
```

---

## Task 4: Update _merge_llm_config for deep merge

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:116-131`

**Step 1: Update _merge_llm_config method**

Replace the method:

```python
def _merge_llm_config(self, agent_llm: dict[str, Any] | None) -> LLMConfig:
    """
    Deep merge agent's llm config with global defaults.

    Args:
        agent_llm: Optional dict of llm overrides from agent frontmatter

    Returns:
        LLMConfig with merged settings
    """
    base = self.config.llm.model_dump()
    if agent_llm:
        base = {**base, **agent_llm}
    return LLMConfig(**base)
```

**Step 2: Run tests**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing::test_parse_simple_agent -v`
Expected: PASS (simple agent with no llm block works)

**Step 3: Commit**

```bash
git add src/picklebot/core/agent_loader.py
git commit -m "refactor(agent): update _merge_llm_config for deep merge"
```

---

## Task 5: Update tests for nested llm format

**Files:**
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Update test_parse_agent_with_llm_overrides**

Replace the test:

```python
def test_parse_agent_with_llm_overrides(self, test_config):
    """Parse agent with nested LLM config."""
    agents_dir = test_config.agents_path
    agents_dir.mkdir()
    agent_dir = agents_dir / "pickle"
    agent_dir.mkdir()
    (agent_dir / "AGENT.md").write_text(
        "---\n"
        "name: Pickle\n"
        "llm:\n"
        "  provider: openai\n"
        "  model: gpt-4\n"
        "  temperature: 0.5\n"
        "  max_tokens: 8192\n"
        "---\n"
        "You are a helpful assistant."
    )

    loader = AgentLoader(test_config)
    agent_def = loader.load("pickle")

    assert agent_def.llm.provider == "openai"
    assert agent_def.llm.model == "gpt-4"
    assert agent_def.llm.temperature == 0.5
    assert agent_def.llm.max_tokens == 8192
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing::test_parse_agent_with_llm_overrides -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "test(agent): update tests for nested llm format"
```

---

## Task 6: Add test for deep merge behavior

**Files:**
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Add test for deep merge with partial llm config**

```python
def test_parse_agent_llm_deep_merges_with_global(self, test_config):
    """Agent's llm config should deep merge with global config."""
    agents_dir = test_config.agents_path
    agents_dir.mkdir()
    agent_dir = agents_dir / "pickle"
    agent_dir.mkdir()
    # Only override temperature, should inherit provider/model/api_key from global
    (agent_dir / "AGENT.md").write_text(
        "---\n"
        "name: Pickle\n"
        "llm:\n"
        "  temperature: 0.3\n"
        "---\n"
        "You are a helpful assistant."
    )

    loader = AgentLoader(test_config)
    agent_def = loader.load("pickle")

    # Inherited from global config
    assert agent_def.llm.provider == "openai"
    assert agent_def.llm.model == "gpt-4o-mini"
    # Overridden by agent
    assert agent_def.llm.temperature == 0.3
    # Default from LLMConfig
    assert agent_def.llm.max_tokens == 2048
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing::test_parse_agent_llm_deep_merges_with_global -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "test(agent): add deep merge test for nested llm config"
```

---

## Task 7: Run full test suite and fix any remaining issues

**Files:**
- Various test files

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 2: Fix any failures**

Address any remaining tests that reference `behavior` attribute or flat frontmatter format.

**Step 3: Commit any fixes**

```bash
git add tests/
git commit -m "fix(tests): update remaining tests for nested llm config"
```

---

## Task 8: Migrate cookie agent

**Files:**
- Modify: `default_workspace/agents/cookie/AGENT.md`

**Step 1: Update cookie agent frontmatter**

Change from:
```yaml
---
name: Cookie
description: A focused task-oriented assistant
temperature: 0.3
---
```

To:
```yaml
---
name: Cookie
description: A focused task-oriented assistant
llm:
  temperature: 0.3
---
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add default_workspace/agents/cookie/AGENT.md
git commit -m "refactor(agents): migrate cookie to nested llm config"
```

---

## Task 9: Migrate pickle agent

**Files:**
- Modify: `default_workspace/agents/pickle/AGENT.md`

**Step 1: Update pickle agent frontmatter**

Change from:
```yaml
---
name: Pickle
description: A friendly general-purpose assistant
temperature: 0.7
---
```

To:
```yaml
---
name: Pickle
description: A friendly general-purpose assistant
llm:
  temperature: 0.7
---
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add default_workspace/agents/pickle/AGENT.md
git commit -m "refactor(agents): migrate pickle to nested llm config"
```

---

## Task 10: Final verification and format/lint

**Step 1: Run format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No issues

**Step 2: Run full test suite one more time**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Final commit if any formatting changes**

```bash
git add .
git commit -m "style: format and lint after nested llm config refactor"
```
