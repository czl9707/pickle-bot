# Test Suite Enhancement Design

## Summary

Enhance the test suite by:
1. Creating shared fixtures in `tests/conftest.py` to eliminate duplicated config construction
2. Consolidating redundant tests in `test_config.py`

## Problem

**Config construction duplication:**
- 6+ test files have their own `_create_test_config()` or inline config construction
- Two files define separate `minimal_llm_config` fixtures
- No shared `conftest.py` exists

**Redundant tests:**
- `test_config.py` has 15 tests across 4 classes testing the same Pydantic validators repeatedly
- Each path type (agents, skills, crons, logging, history, memories) has identical test patterns

## Solution

### 1. Shared Fixtures (`tests/conftest.py`)

Create central fixtures that all tests can use:

```python
@pytest.fixture
def llm_config() -> LLMConfig:
    """Minimal LLM config for testing."""
    return LLMConfig(provider="test", model="test-model", api_key="test-key")

@pytest.fixture
def test_config(tmp_path: Path, llm_config: LLMConfig) -> Config:
    """Config with workspace pointing to tmp_path."""
    return Config(workspace=tmp_path, llm=llm_config, default_agent="test")

@pytest.fixture
def test_context(test_config: Config) -> SharedContext:
    """SharedContext with test config."""
    return SharedContext(config=test_config)

@pytest.fixture
def test_agent_def(llm_config: LLMConfig) -> AgentDef:
    """Minimal AgentDef for testing."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        system_prompt="You are a test assistant.",
        llm=llm_config,
        behavior=AgentBehaviorConfig(),
    )

@pytest.fixture
def test_agent(test_context: SharedContext, test_agent_def: AgentDef) -> Agent:
    """Agent instance for testing."""
    return Agent(agent_def=test_agent_def, context=test_context)
```

### 2. Test Consolidation

**`test_config.py`:** Reduce from 15 tests to 6 focused tests

Before:
- `TestAgentsPath` (4 tests)
- `TestPathResolution` (5 tests)
- `TestRejectsAbsolutePaths` (4 tests)
- Plus duplicate fixture

After:
- `TestPathResolution` (2 tests) - one for resolution, one for rejection
- `TestConfigValidation` (1 test) - required fields
- Plus shared `llm_config` fixture from conftest.py

**Removes:** 9 redundant per-path tests that verify the same validator behavior

### 3. Files to Modify

| File | Change |
|------|--------|
| `tests/conftest.py` | Create with shared fixtures |
| `tests/utils/test_config.py` | Consolidate path tests |
| `tests/core/test_context.py` | Use `test_config`, `test_context` |
| `tests/core/test_agent.py` | Use `test_config`, `test_agent_def` |
| `tests/core/test_session.py` | Use `test_agent` |
| `tests/core/test_messagebus_executor.py` | Use `test_config`, `test_context` |
| `tests/tools/test_subagent_tool.py` | Use `test_config` |
| `tests/cli/test_server.py` | Use `test_config` |
| `tests/utils/test_config_validation.py` | Use shared `llm_config` |

### 4. Files Unchanged

These files already have good structure or no config dependency:
- `test_history.py` - Already has fixtures
- `test_agent_loader.py` - Uses isolated LLM fixtures
- `test_skill_loader.py` - No config dependency
- `test_skill_tool.py` - No config dependency
- `test_cron_executor.py` - No config dependency

## Impact

- **Test count:** ~85 → ~76 tests (removing redundancy)
- **Maintainability:** Single source of truth for test fixtures
- **Readability:** Tests focus on behavior, not setup
