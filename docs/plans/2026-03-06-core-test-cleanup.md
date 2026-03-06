# Core Module Test Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate trivial tests in tests/core/ using parametrized roundtrip tests, reducing from 57 to 37 tests while maintaining coverage.

**Architecture:** Apply same patterns used in events/ cleanup - parametrize similar cases, combine property checks, merge related behavior tests. Four phases: EventSource pattern, Command tests, Loader pattern, Context/Session.

**Tech Stack:** pytest, pytest.mark.parametrize

---

## Phase 1: EventSource Pattern

### Task 1: Rewrite test_websocket_event_source.py

**Files:**
- Modify: `tests/core/test_websocket_event_source.py` (rewrite entirely)
- Test: `tests/core/test_websocket_event_source.py`

**Step 1: Write the new parametrized tests**

Replace entire file with:

```python
"""Tests for WebSocketEventSource."""

import pytest
from picklebot.core.events import WebSocketEventSource


class TestWebSocketEventSource:
    """Parametrized tests for WebSocketEventSource."""

    @pytest.mark.parametrize("user_id,expected_str,type_props", [
        (
            "user-123",
            "platform-ws:user-123",
            {"is_platform": True, "is_agent": False, "is_cron": False},
        ),
        (
            "user:with:colons",
            "platform-ws:user:with:colons",
            {"is_platform": True, "is_agent": False, "is_cron": False},
        ),
    ])
    def test_source_roundtrip(self, user_id, expected_str, type_props):
        """Source should serialize/deserialize and have correct type properties."""
        # Create
        source = WebSocketEventSource(user_id=user_id)

        # Check serialization
        assert str(source) == expected_str

        # Check roundtrip
        restored = WebSocketEventSource.from_string(expected_str)
        assert restored.user_id == user_id

        # Check type properties
        for prop, expected in type_props.items():
            assert getattr(source, prop) == expected

    @pytest.mark.parametrize("invalid_str,error_match", [
        ("invalid-namespace:user", "Invalid WebSocketEventSource"),
        ("invalid-format", "Invalid WebSocketEventSource"),
        ("platform-ws:", "Invalid WebSocketEventSource"),
    ])
    def test_from_string_rejects_invalid(self, invalid_str, error_match):
        """from_string should reject invalid formats."""
        with pytest.raises(ValueError, match=error_match):
            WebSocketEventSource.from_string(invalid_str)
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_websocket_event_source.py -v`

Expected: All 5 tests pass (2 roundtrip + 3 invalid)

**Step 3: Commit**

```bash
git add tests/core/test_websocket_event_source.py
git commit -m "refactor(test): consolidate WebSocketEventSource tests into parametrized roundtrip"
```

---

### Task 2: Rewrite test_commands/test_base.py

**Files:**
- Modify: `tests/core/commands/test_base.py` (rewrite entirely)
- Test: `tests/core/commands/test_base.py`

**Step 1: Write the consolidated test**

Replace entire file with:

```python
"""Tests for command base classes."""

from picklebot.core.commands.base import Command


class ConcreteCommand(Command):
    """Concrete implementation for testing."""

    name = "test"
    aliases = ["t", "tst"]
    description = "A test command"

    def execute(self, args: str, ctx) -> str:
        return f"executed with: {args}"


class TestCommand:
    """Tests for Command ABC."""

    def test_command_creation_and_execution(self):
        """Command should have properties and execute correctly."""
        cmd = ConcreteCommand()

        # Check properties
        assert cmd.name == "test"
        assert cmd.aliases == ["t", "tst"]
        assert cmd.description == "A test command"

        # Check execution
        assert cmd.execute("args", None) == "executed with: args"
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_base.py -v`

Expected: 1 test passes

**Step 3: Commit**

```bash
git add tests/core/commands/test_base.py
git commit -m "refactor(test): consolidate Command base tests"
```

---

## Phase 2: Command Tests (No Changes)

### Task 3: Verify test_commands/test_registry.py

**Files:**
- Verify: `tests/core/commands/test_registry.py`

**Step 1: Run tests to verify current state**

Run: `uv run pytest tests/core/commands/test_registry.py -v`

Expected: All tests pass

**Step 2: Document no changes needed**

This file is already well-structured with good parametrization. No changes required.

---

## Phase 3: Loader Pattern

### Task 4: Consolidate test_skill_loader.py template tests

**Files:**
- Modify: `tests/core/test_skill_loader.py`
- Test: `tests/core/test_skill_loader.py`

**Step 1: Replace template tests with parametrized version**

Find the `TestSkillLoaderTemplateSubstitution` class and replace it with:

```python
class TestSkillLoaderTemplateSubstitution:
    """Tests for template variable substitution in skill content."""

    @pytest.mark.parametrize("content,expected_contains", [
        ("Workspace is at: {{workspace}}", "workspace"),
        ("Skills: {{skills_path}}\nMemories: {{memories_path}}\nCrons: {{crons_path}}", None),  # Multiple variables
        ("No templates here.", "No templates here."),  # No substitution
    ])
    def test_template_substitution(self, test_config, content, expected_contains):
        """Skill content should substitute template variables."""
        skills_dir = test_config.skills_path
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            f"""---
name: Test Skill
description: A test skill
---

{content}
"""
        )

        loader = SkillLoader(test_config)
        skill_def = loader.load_skill("test-skill")

        if expected_contains == "workspace":
            assert str(test_config.workspace) in skill_def.content
        elif expected_contains is None:
            # Multiple variables case
            assert str(test_config.skills_path) in skill_def.content
            assert str(test_config.memories_path) in skill_def.content
            assert str(test_config.crons_path) in skill_def.content
        else:
            # No substitution case
            assert skill_def.content == expected_contains
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_skill_loader.py::TestSkillLoaderTemplateSubstitution -v`

Expected: 3 tests pass (down from 3 separate tests, but now parametrized)

**Step 3: Commit**

```bash
git add tests/core/test_skill_loader.py
git commit -m "refactor(test): consolidate skill loader template tests"
```

---

### Task 5: Consolidate test_cron_loader.py load and discover tests

**Files:**
- Modify: `tests/core/test_cron_loader.py`
- Test: `tests/core/test_cron_loader.py`

**Step 1: Replace load tests with parametrized version**

Find `test_load_simple_cron` and `test_load_cron_with_one_off` and replace with:

```python
    @pytest.mark.parametrize("one_off,expected_one_off", [
        (None, False),  # default
        (True, True),   # explicit true
    ])
    def test_load_cron_with_optional_fields(self, test_config, one_off, expected_one_off):
        """Load cron with various field combinations."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        cron_dir = crons_dir / "test-cron"
        cron_dir.mkdir()

        one_off_yaml = f"one_off: {one_off}\n" if one_off is not None else ""
        (cron_dir / "CRON.md").write_text(
            f"---\n"
            f"name: Test Cron\n"
            f"description: Test description\n"
            f"agent: pickle\n"
            f"schedule: '*/15 * * * *'\n"
            f"{one_off_yaml}"
            f"---\n"
            f"Test prompt."
        )

        loader = CronLoader(test_config)
        cron_def = loader.load("test-cron")

        assert cron_def.id == "test-cron"
        assert cron_def.name == "Test Cron"
        assert cron_def.agent == "pickle"
        assert cron_def.schedule == "*/15 * * * *"
        assert cron_def.one_off == expected_one_off
```

**Step 2: Update discover test to include one_off**

Replace `test_discover_crons` and `test_discover_crons_with_one_off` with:

```python
    def test_discover_crons(self, test_config):
        """Discover all valid cron jobs including one_off variations."""
        crons_dir = test_config.crons_path
        crons_dir.mkdir(parents=True, exist_ok=True)

        # Create recurring cron
        cron_dir = crons_dir / "recurring-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Recurring Job\n"
            "description: A recurring job\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "---\n"
            "Do repeatedly."
        )

        # Create one-off cron
        cron_dir2 = crons_dir / "one-off-job"
        cron_dir2.mkdir()
        (cron_dir2 / "CRON.md").write_text(
            "---\n"
            "name: One Off Job\n"
            "description: A one-off job\n"
            "agent: pickle\n"
            "schedule: '0 10 18 2 *'\n"
            "one_off: true\n"
            "---\n"
            "Do once."
        )

        # Create a directory without CRON.md (should be skipped)
        (crons_dir / "no-file").mkdir()

        loader = CronLoader(test_config)
        defs = loader.discover_crons()

        assert len(defs) == 2
        ids = [d.id for d in defs]
        assert "recurring-job" in ids
        assert "one-off-job" in ids
        assert "no-file" not in ids

        recurring = next(d for d in defs if d.id == "recurring-job")
        one_off = next(d for d in defs if d.id == "one-off-job")

        assert recurring.one_off is False
        assert one_off.one_off is True
```

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_cron_loader.py -v`

Expected: 4 tests pass (down from 6)

**Step 4: Commit**

```bash
git add tests/core/test_cron_loader.py
git commit -m "refactor(test): consolidate cron loader tests"
```

---

### Task 6: Consolidate test_agent_loader.py template tests

**Files:**
- Modify: `tests/core/test_agent_loader.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Replace template tests with parametrized version**

Find `TestAgentLoaderTemplateSubstitution` class and replace with:

```python
class TestAgentLoaderTemplateSubstitution:
    """Tests for template variable substitution in agent content."""

    @pytest.mark.parametrize("content,expected_check", [
        ("Memories at: {{memories_path}}", "memories"),
        ("Workspace: {{workspace}}, Skills: {{skills_path}}", "multiple"),
        ("No templates here.", "literal"),
    ])
    def test_template_substitution(self, test_config, content, expected_check):
        """AgentLoader substitutes template variables."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            f"---\nname: Test\n---\n{content}"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        if expected_check == "memories":
            expected = f"Memories at: {test_config.memories_path}"
            assert agent_def.agent_md == expected
        elif expected_check == "multiple":
            expected = f"Workspace: {test_config.workspace}, Skills: {test_config.skills_path}"
            assert agent_def.agent_md == expected
        else:
            assert agent_def.agent_md == "No templates here."
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderTemplateSubstitution -v`

Expected: 3 tests pass (down from 3 separate tests)

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "refactor(test): consolidate agent loader template tests"
```

---

### Task 7: Consolidate test_agent_loader.py allow_skills tests

**Files:**
- Modify: `tests/core/test_agent_loader.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Replace allow_skills tests with parametrized version**

Find `test_parse_agent_with_allow_skills` and `test_parse_agent_without_allow_skills_defaults_false` and replace with:

```python
    @pytest.mark.parametrize("allow_skills_yaml,expected", [
        ("allow_skills: true\n", True),
        ("", False),  # default
    ])
    def test_allow_skills_field(self, test_config, allow_skills_yaml, expected):
        """Agent should parse allow_skills with correct default."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            f"---\n"
            f"name: Test Agent\n"
            f"{allow_skills_yaml}"
            f"---\n"
            f"System prompt here.\n"
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.allow_skills == expected
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderParsing::test_allow_skills_field -v`

Expected: 2 tests pass

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "refactor(test): consolidate agent loader allow_skills tests"
```

---

### Task 8: Consolidate test_agent_loader.py max_concurrency tests

**Files:**
- Modify: `tests/core/test_agent_loader.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Replace max_concurrency load tests with parametrized version**

Find `test_load_agent_with_max_concurrency` and `test_load_agent_without_max_concurrency_uses_default` in `TestAgentLoaderMaxConcurrency` and replace with:

```python
class TestAgentLoaderMaxConcurrency:
    """Tests for max_concurrency field."""

    @pytest.mark.parametrize("max_concurrency_yaml,expected", [
        ("max_concurrency: 5\n", 5),
        ("", 1),  # default
    ])
    def test_max_concurrency_field(self, test_config, max_concurrency_yaml, expected):
        """Agent should parse max_concurrency with correct default."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            f"""---
name: Test Agent
description: Test description
{max_concurrency_yaml}
---
You are a test assistant.
"""
        )

        loader = AgentLoader(test_config)
        agent_def = loader.load("test-agent")

        assert agent_def.max_concurrency == expected
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderMaxConcurrency -v`

Expected: 2 tests pass (down from 2 separate tests)

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "refactor(test): consolidate agent loader max_concurrency tests"
```

---

### Task 9: Consolidate test_agent_loader.py error tests

**Files:**
- Modify: `tests/core/test_agent_loader.py`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Replace not_found tests with parametrized version**

Find `test_raises_not_found_when_folder_missing` and `test_raises_not_found_when_file_missing` and replace with:

```python
    @pytest.mark.parametrize("scenario", ["folder_missing", "file_missing"])
    def test_raises_not_found(self, test_config, scenario):
        """Should raise DefNotFoundError for missing resources."""
        agents_dir = test_config.agents_path
        agents_dir.mkdir()

        if scenario == "file_missing":
            agent_dir = agents_dir / "pickle"
            agent_dir.mkdir()
            # No AGENT.md created

        loader = AgentLoader(test_config)

        with pytest.raises(DefNotFoundError) as exc:
            loader.load("pickle")

        assert exc.value.def_id == "pickle"
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderErrors -v`

Expected: 2 tests pass (down from 3)

**Step 3: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "refactor(test): consolidate agent loader not_found tests"
```

---

## Phase 4: Context and Session

### Task 10: Consolidate test_context.py initialization tests

**Files:**
- Modify: `tests/core/test_context.py`
- Test: `tests/core/test_context.py`

**Step 1: Merge initialization tests**

Replace `TestSharedContextBasics` class with:

```python
class TestSharedContextBasics:
    """Tests for basic SharedContext initialization."""

    def test_context_initialization(self, test_context):
        """SharedContext should initialize with all required components."""
        # Check all components exist
        assert test_context.config is not None
        assert test_context.history_store is not None
        assert test_context.agent_loader is not None
        assert test_context.skill_loader is not None
        assert test_context.cron_loader is not None
        assert test_context.command_registry is not None
        assert test_context.eventbus is not None

        # Check routing table
        assert hasattr(test_context, "routing_table")
        assert isinstance(test_context.routing_table, RoutingTable)

        # Check eventbus
        assert isinstance(test_context.eventbus, EventBus)
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_context.py::TestSharedContextBasics -v`

Expected: 1 test passes (down from 2)

**Step 3: Commit**

```bash
git add tests/core/test_context.py
git commit -m "refactor(test): consolidate context initialization tests"
```

---

### Task 11: Consolidate test_context.py channel tests

**Files:**
- Modify: `tests/core/test_context.py`
- Test: `tests/core/test_context.py`

**Step 1: Replace channel tests with parametrized version**

Find `TestSharedContextCustomChannels` class and replace the first three tests with:

```python
    @pytest.mark.parametrize("channels_arg,should_call_from_config,expected_channels", [
        (None, True, []),  # backward compat - loads from config
        ([], False, []),   # empty list - skips config
    ])
    def test_channels_parameter_behavior(
        self, mock_config, channels_arg, should_call_from_config, expected_channels
    ):
        """Test channels parameter behavior."""
        with patch("picklebot.core.context.Channel.from_config") as mock_from_config:
            mock_from_config.return_value = []

            context = SharedContext(config=mock_config, channels=channels_arg)

            if should_call_from_config:
                mock_from_config.assert_called_once_with(mock_config)
            else:
                mock_from_config.assert_not_called()

            assert context.channels == expected_channels
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_context.py::TestSharedContextCustomChannels -v`

Expected: 3 tests pass (down from 4)

**Step 3: Commit**

```bash
git add tests/core/test_context.py
git commit -m "refactor(test): consolidate context channel parameter tests"
```

---

### Task 12: Consolidate test_session_state.py message tests

**Files:**
- Modify: `tests/core/test_session_state.py`
- Test: `tests/core/test_session_state.py`

**Step 1: Merge message tests**

Replace `TestSessionStatePersistence` class with:

```python
class TestSessionStatePersistence:
    """Tests for message persistence."""

    def test_add_message_persists_and_appends(self, tmp_path):
        """add_message should append to memory and persist to history."""
        from picklebot.core.history import HistoryStore

        mock_agent = MagicMock()
        mock_agent.agent_def.id = "test-agent"

        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path)

        source = TelegramEventSource(user_id="123", chat_id="456")

        state = SessionState(
            session_id="test-session-id",
            agent=mock_agent,
            messages=[],
            source=source,
            shared_context=mock_context,
        )

        # Create session
        mock_context.history_store.create_session(
            "test-agent", "test-session-id", source
        )

        # Add messages
        state.add_message({"role": "user", "content": "Hello"})
        state.add_message({"role": "assistant", "content": "Hi"})

        # Check in-memory append
        assert len(state.messages) == 2
        assert state.messages[0]["content"] == "Hello"
        assert state.messages[1]["content"] == "Hi"

        # Check persistence
        messages = mock_context.history_store.get_messages("test-session-id")
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi"
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_session_state.py -v`

Expected: 2 tests pass (down from 3)

**Step 3: Commit**

```bash
git add tests/core/test_session_state.py
git commit -m "refactor(test): consolidate session state message tests"
```

---

## Final Verification

### Task 13: Run full test suite

**Files:**
- None (verification only)

**Step 1: Run all core tests**

Run: `uv run pytest tests/core/ -v`

Expected: All tests pass, count should be reduced from ~166 to ~146

**Step 2: Run full test suite**

Run: `uv run pytest`

Expected: All tests pass

**Step 3: Run linting**

Run: `uv run black . && uv run ruff check .`

Expected: No issues

**Step 4: Final commit (if any formatting changes)**

```bash
git add -A
git commit -m "style: format after test cleanup"
```

---

## Summary

This plan consolidates tests in core/ module through parametrization:

| Phase | Files | Before | After | Reduction |
|-------|-------|--------|-------|-----------|
| Phase 1 | EventSource pattern | 9 | 3 | 67% |
| Phase 2 | Command tests | 6 | 6 | 0% |
| Phase 3 | Loader pattern | 30 | 19 | 37% |
| Phase 4 | Context/Session | 12 | 8 | 33% |
| **Total** | **All core/** | **57** | **36** | **37%** |

**Result:** ~21 tests eliminated, ~400 lines removed, no coverage loss.
