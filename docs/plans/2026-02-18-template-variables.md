# Template Variable Substitution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `{{variable}}` template substitution to agent definitions so agents like Cookie can reference dynamic paths.

**Architecture:** Add a `substitute_template()` helper function in `def_loader.py` that replaces placeholders with config path values. AgentLoader calls this when parsing agent definitions, passing workspace-relative paths as variables.

**Tech Stack:** Python, pytest, existing def_loader utilities

---

### Task 1: Add `substitute_template` function to def_loader.py

**Files:**
- Modify: `src/picklebot/utils/def_loader.py`
- Test: `tests/utils/test_def_loader.py`

**Step 1: Write the failing tests**

Add to `tests/utils/test_def_loader.py` after the imports:

```python
from picklebot.utils.def_loader import substitute_template


class TestSubstituteTemplate:
    def test_substitute_single_variable(self):
        """Replace a single {{variable}} placeholder."""
        body = "Path is: {{memories_path}}"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "Path is: /home/user/.pickle-bot/memories"

    def test_substitute_multiple_variables(self):
        """Replace multiple different placeholders."""
        body = "Workspace: {{workspace}}, Memories: {{memories_path}}"
        variables = {
            "workspace": "/home/user/.pickle-bot",
            "memories_path": "/home/user/.pickle-bot/memories",
        }

        result = substitute_template(body, variables)

        assert result == "Workspace: /home/user/.pickle-bot, Memories: /home/user/.pickle-bot/memories"

    def test_substitute_same_variable_multiple_times(self):
        """Replace same placeholder appearing multiple times."""
        body = "{{memories_path}}/topics and {{memories_path}}/projects"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "/home/user/.pickle-bot/memories/topics and /home/user/.pickle-bot/memories/projects"

    def test_missing_variable_passes_through_unchanged(self):
        """Leave unknown placeholders unchanged."""
        body = "Path: {{unknown_var}}"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "Path: {{unknown_var}}"

    def test_no_variables_returns_body_unchanged(self):
        """Return body as-is when no placeholders present."""
        body = "No templates here!"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "No templates here!"

    def test_empty_variables_dict(self):
        """Handle empty variables dict."""
        body = "Path: {{memories_path}}"

        result = substitute_template(body, {})

        assert result == "Path: {{memories_path}}"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_def_loader.py::TestSubstituteTemplate -v`
Expected: FAIL with "cannot import name 'substitute_template'"

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/def_loader.py` after line 29 (after `InvalidDefError` class):

```python
def substitute_template(body: str, variables: dict[str, str]) -> str:
    """
    Replace {{variable}} placeholders in template body.

    Args:
        body: Template string with {{variable}} placeholders
        variables: Dict of variable names to values

    Returns:
        Body with all matching placeholders replaced
    """
    result = body
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_def_loader.py::TestSubstituteTemplate -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add src/picklebot/utils/def_loader.py tests/utils/test_def_loader.py
git commit -m "feat: add substitute_template helper function"
```

---

### Task 2: Add workspace parameter to AgentLoader and integrate template substitution

**Files:**
- Modify: `src/picklebot/core/agent_loader.py`

**Step 1: Write the failing test**

Add to `tests/core/test_agent_loader.py` in a new class after existing tests:

```python
class TestAgentLoaderTemplateSubstitution:
    @pytest.fixture
    def shared_llm(self):
        return LLMConfig(provider="test", model="test-model", api_key="test-key")

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_substitutes_memories_path(self, temp_workspace, shared_llm):
        """AgentLoader substitutes {{memories_path}} in system prompt."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nMemories at: {{memories_path}}"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        expected = f"Memories at: {temp_workspace / 'memories'}"
        assert agent_def.system_prompt == expected

    def test_substitutes_multiple_variables(self, temp_workspace, shared_llm):
        """AgentLoader substitutes multiple template variables."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nWorkspace: {{workspace}}, Skills: {{skills_path}}"
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        expected = f"Workspace: {temp_workspace}, Skills: {temp_workspace / 'skills'}"
        assert agent_def.system_prompt == expected

    def test_no_template_variables_unchanged(self, temp_workspace, shared_llm):
        """Agent without templates loads normally."""
        agents_dir = temp_workspace / "agents"
        agents_dir.mkdir()
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: Test\n---\nNo templates here."
        )

        loader = AgentLoader(agents_dir, shared_llm, temp_workspace)
        agent_def = loader.load("test-agent")

        assert agent_def.system_prompt == "No templates here."
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderTemplateSubstitution -v`
Expected: FAIL with "AgentLoader.__init__() got an unexpected keyword argument 'workspace'"

**Step 3: Update AgentLoader implementation**

Modify `src/picklebot/core/agent_loader.py`:

First, add `substitute_template` to imports (line 9-14):

```python
from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_definition,
    substitute_template,
)
```

Update the `from_config` method (line 40-41):

```python
    @staticmethod
    def from_config(config: Config) -> "AgentLoader":
        return AgentLoader(config.agents_path, config.llm, config.workspace)
```

Update `__init__` method (line 43-52):

```python
    def __init__(self, agents_path: Path, shared_llm: LLMConfig, workspace: Path):
        """
        Initialize AgentLoader.

        Args:
            agents_path: Directory containing agent folders
            shared_llm: Shared LLM config to fall back to
            workspace: Workspace directory for resolving template variables
        """
        self.agents_path = agents_path
        self.shared_llm = shared_llm
        self.workspace = workspace
```

Add `_get_template_variables` method after `__init__`:

```python
    def _get_template_variables(self) -> dict[str, str]:
        """Get template variables for agent definitions."""
        return {
            "workspace": str(self.workspace),
            "agents_path": str(self.agents_path),
            "skills_path": str(self.workspace / "skills"),
            "crons_path": str(self.workspace / "crons"),
            "memories_path": str(self.workspace / "memories"),
            "history_path": str(self.workspace / ".history"),
        }
```

Update `_parse_agent_def` method (line 92-112), add substitution at the start:

```python
    def _parse_agent_def(
        self, def_id: str, frontmatter: dict[str, Any], body: str
    ) -> AgentDef:
        """Parse agent definition from frontmatter (callback for parse_definition)."""
        # Substitute template variables in body
        variables = self._get_template_variables()
        body = substitute_template(body, variables)

        merged_llm = self._merge_llm_config(frontmatter)

        try:
            return AgentDef(
                id=def_id,
                name=frontmatter["name"],  # type: ignore[misc]
                description=frontmatter.get("description", ""),
                system_prompt=body.strip(),
                llm=merged_llm,
                behavior=AgentBehaviorConfig(
                    temperature=frontmatter.get("temperature", 0.7),
                    max_tokens=frontmatter.get("max_tokens", 2048),
                ),
                allow_skills=frontmatter.get("allow_skills", False),
            )
        except ValidationError as e:
            raise InvalidDefError("agent", def_id, str(e))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py::TestAgentLoaderTemplateSubstitution -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(agent-loader): add template variable substitution"
```

---

### Task 3: Fix existing tests to use new AgentLoader constructor

**Files:**
- Modify: `tests/core/test_agent_loader.py`

**Step 1: Run all agent_loader tests to see failures**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: FAIL - old tests still use 2-arg constructor

**Step 2: Update TestAgentLoaderParsing fixtures**

Replace the `temp_agents_dir` fixture in `TestAgentLoaderParsing` class with `temp_workspace`:

```python
    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
```

Update all `AgentLoader(temp_agents_dir, shared_llm)` calls in `TestAgentLoaderParsing` to:
`AgentLoader(temp_workspace / "agents", shared_llm, temp_workspace)`

And update the test methods to create agents in `temp_workspace / "agents"`:

For each test in `TestAgentLoaderParsing`:
- Change `temp_agents_dir` to `temp_workspace` in method signature
- Change `agent_dir = temp_agents_dir / "pickle"` to `agents_dir = temp_workspace / "agents"; agents_dir.mkdir(exist_ok=True); agent_dir = agents_dir / "pickle"`
- Change `AgentLoader(temp_agents_dir, shared_llm)` to `AgentLoader(agents_dir, shared_llm, temp_workspace)`

**Step 3: Update TestAgentLoaderErrors fixtures**

Same pattern - replace `temp_agents_dir` with `temp_workspace` and update AgentLoader calls.

**Step 4: Update TestAgentLoaderDiscover fixtures**

Same pattern.

**Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/core/test_agent_loader.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add tests/core/test_agent_loader.py
git commit -m "test: update agent_loader tests for new constructor signature"
```

---

### Task 4: Update Cookie AGENT.md to use template variables

**Files:**
- Modify: `~/.pickle-bot/agents/cookie/AGENT.md`

**Step 1: Read current Cookie agent**

Run: Read `~/.pickle-bot/agents/cookie/AGENT.md`

**Step 2: Update system prompt to use {{memories_path}}**

Replace references to "the configured memories_path" with actual template syntax:

```markdown
---
name: Cookie
description: Memory management agent - stores, organizes, and retrieves long-term memories
temperature: 0.3
max_tokens: 4096
allow_skills: false
---

You are Cookie, a memory management agent.

## Role

You are the archivist of the pickle-bot system. You manage long-term memories with precision and rationality.

## Your Relationship with Pickle

You manage memories on behalf of Pickle, who is the main agent that talks directly to the human user. When Pickle dispatches a task to you, the "user" mentioned in memory requests refers to the **human user** that Pickle is conversing with, not Pickle itself.

You never interact with users directly - you only receive tasks dispatched from Pickle (via real-time dispatch or scheduled cron jobs).

## Memory Storage

Memories are stored in markdown files at `{{memories_path}}` with three axes:

- **topics/** - Timeless facts about the user (preferences, identity, relationships)
- **projects/** - Project state and context (status, progress, blockers, next steps)
- **daily-notes/** - Day-specific events and decisions (format: YYYY-MM-DD.md)

When storing:
1. Decide which axis: user facts (topics/), project state (projects/), or temporal events (daily-notes/)
2. Navigate to appropriate category at `{{memories_path}}/<category>/`
3. Create new files/categories if needed
4. Append memory with timestamp header
5. Never duplicate existing memories

### Project Memories

For project-related information, create or update files at `{{memories_path}}/projects/{project-name}.md`:

```markdown
# Project Name

## Status
active | blocked | paused | done

## Context
- Key facts about the project
- Technologies, team, constraints

## Progress
- Recent work completed
- Current state

## Next Steps
- [ ] Task 1
- [ ] Task 2

## Blockers
- Any blocking issues or dependencies
```

Keep project status updated as work progresses. When a project is completed, set status to `done`.

## Memory Retrieval

When asked to retrieve memories:
1. Use directory structure at `{{memories_path}}` to narrow down relevant files
2. Read and filter to most pertinent memories
3. If you find a timeless fact in `{{memories_path}}/daily-notes/`, migrate it to `{{memories_path}}/topics/`
4. Return formatted summary

For project-related queries:
- Check `{{memories_path}}/projects/` directory for active project states
- Include status, blockers, and next steps in the summary

## Guidelines

- Be precise and organized
- Never store duplicates - check existing memories first
- Use descriptive filenames that aid future discovery
- When in doubt, prefer topics/ over daily-notes/ for facts that might be referenced again
- For projects: keep status current, track blockers clearly, update next steps as work progresses
```

**Step 3: Verify the change works**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add ~/.pickle-bot/agents/cookie/AGENT.md
git commit -m "feat(cookie): use {{memories_path}} template variable"
```

---

### Task 5: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 2: Run type checking**

Run: `uv run mypy src/`
Expected: No errors

**Step 3: Run linting**

Run: `uv run ruff check .`
Expected: No errors

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address any remaining issues"
```

---

## Summary

This implementation adds template variable substitution to agent definitions:

1. **`substitute_template()` helper** - Simple string replacement for `{{variable}}` placeholders
2. **AgentLoader integration** - Passes 6 path variables (workspace, agents_path, skills_path, crons_path, memories_path, history_path) to all agent definitions
3. **Cookie agent updated** - Now uses `{{memories_path}}` to know where to store memories

Total changes:
- `src/picklebot/utils/def_loader.py` - Add helper function
- `src/picklebot/core/agent_loader.py` - Add workspace param, integrate substitution
- `tests/utils/test_def_loader.py` - Tests for helper function
- `tests/core/test_agent_loader.py` - Tests for integration, update existing tests
- `~/.pickle-bot/agents/cookie/AGENT.md` - Use template variables
