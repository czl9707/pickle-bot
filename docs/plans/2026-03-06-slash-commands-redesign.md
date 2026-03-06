# Slash Commands Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign slash commands to support detail views and add routing management.

**Architecture:** Modify existing command handlers to support optional ID argument for detail view. Add RouteCommand and BindingsCommand for routing management. Persist route bindings to config.user.yaml.

**Tech Stack:** Python, pytest, pydantic

---

### Task 1: Update AgentCommand for detail view

**Files:**
- Modify: `src/picklebot/core/commands/handlers.py:96-128`
- Modify: `tests/core/commands/test_handlers.py:78-179`

**Step 1: Write the failing tests**

Add tests for AgentCommand detail view in `tests/core/commands/test_handlers.py`:

```python
def test_agent_show_detail(self, mock_session, mock_context):
    """Test agent command shows detail for specific agent."""
    from picklebot.core.agent_loader import AgentDef
    from picklebot.utils.config import LLMConfig

    llm_config = LLMConfig(provider="test", model="test-model", api_key="test-key")
    mock_agent = MagicMock()
    mock_agent.agent_def = AgentDef(
        id="current-agent",
        name="Current Agent",
        description="Current agent desc",
        agent_md="You are current.",
        soul_md="Be friendly.",
        llm=llm_config,
    )
    mock_session.agent = mock_agent
    mock_session.shared_context = mock_context
    mock_context.agent_loader.load.return_value = mock_agent.agent_def

    cmd = AgentCommand()
    result = cmd.execute("current-agent", mock_session)

    assert "**Agent:** `current-agent`" in result
    assert "**Name:** Current Agent" in result
    assert "**Description:** Current agent desc" in result
    mock_context.agent_loader.load.assert_called_once_with("current-agent")

def test_agent_show_detail_not_found(self, mock_session, mock_context):
    """Test agent command handles non-existent agent."""
    mock_session.shared_context = mock_context
    mock_context.agent_loader.load.side_effect = ValueError("not found")

    cmd = AgentCommand()
    result = cmd.execute("nonexistent", mock_session)

    assert "not found" in result
```

Remove the old switch tests (`test_agent_switch_success`, `test_agent_switch_not_found`).

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute::test_agent_show_detail -v`
Expected: FAIL - AgentCommand still switches instead of showing detail

**Step 3: Update AgentCommand**

In `src/picklebot/core/commands/handlers.py`, replace `AgentCommand`:

```python
class AgentCommand(Command):
    """List agents or show agent details."""

    name = "agent"
    aliases = ["agents"]
    description = "List agents or show agent details"

    def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            # List agents
            agents = session.shared_context.agent_loader.discover_agents()
            lines = ["**Agents:**"]
            for agent in agents:
                marker = " (current)" if agent.id == session.agent.agent_def.id else ""
                lines.append(f"- `{agent.id}`: {agent.name}{marker}")
            return "\n".join(lines)

        # Show specific agent details
        agent_id = args.strip()
        try:
            agent_def = session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        lines = [
            f"**Agent:** `{agent_def.id}`",
            f"**Name:** {agent_def.name}",
            f"**Description:** {agent_def.description}",
            f"**LLM:** {agent_def.llm.model}",
        ]

        # Add content sections
        lines.append(f"\n---\n\n**AGENT.md:**\n```\n{agent_def.agent_md}\n```")

        if agent_def.soul_md:
            lines.append(f"\n**SOUL.md:**\n```\n{agent_def.soul_md}\n```")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute -v`
Expected: PASS

**Step 5: Update test parametrized properties**

In `tests/core/commands/test_handlers.py`, update the `test_command_properties` parametrize to reflect new description:

```python
(
    AgentCommand,
    "agent",
    ["agents"],
    "List agents or show agent details",
),
```

**Step 6: Run full test suite**

Run: `uv run pytest tests/core/commands/ -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/picklebot/core/commands/handlers.py tests/core/commands/test_handlers.py
git commit -m "refactor: change /agent to show details instead of switch"
```

---

### Task 2: Update SkillsCommand for detail view

**Files:**
- Modify: `src/picklebot/core/commands/handlers.py:131-145`
- Modify: `tests/core/commands/test_handlers.py:131-137`

**Step 1: Write the failing tests**

Add tests in `tests/core/commands/test_handlers.py`:

```python
def test_skills_show_detail(self, mock_session, mock_context):
    """Test skills command shows detail for specific skill."""
    from picklebot.core.skill_loader import SkillDef

    mock_skill = SkillDef(
        id="brainstorm",
        name="Brainstorming",
        description="Turn ideas into designs",
        content="## How to brainstorm\n\nFollow these steps...",
    )
    mock_session.shared_context = mock_context
    mock_context.skill_loader.load_skill.return_value = mock_skill

    cmd = SkillsCommand()
    result = cmd.execute("brainstorm", mock_session)

    assert "**Skill:** `brainstorm`" in result
    assert "**Name:** Brainstorming" in result
    assert "**Description:** Turn ideas into designs" in result
    assert "## How to brainstorm" in result
    mock_context.skill_loader.load_skill.assert_called_once_with("brainstorm")

def test_skills_show_detail_not_found(self, mock_session, mock_context):
    """Test skills command handles non-existent skill."""
    from picklebot.utils.def_loader import DefNotFoundError

    mock_session.shared_context = mock_context
    mock_context.skill_loader.load_skill.side_effect = DefNotFoundError("skill", "nonexistent")

    cmd = SkillsCommand()
    result = cmd.execute("nonexistent", mock_session)

    assert "not found" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute::test_skills_show_detail -v`
Expected: FAIL

**Step 3: Update SkillsCommand**

In `src/picklebot/core/commands/handlers.py`:

```python
class SkillsCommand(Command):
    """List all skills or show skill details."""

    name = "skills"
    description = "List all skills or show skill details"

    def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            skills = session.shared_context.skill_loader.discover_skills()
            if not skills:
                return "No skills configured."

            lines = ["**Skills:**"]
            for skill in skills:
                lines.append(f"- `{skill.id}`: {skill.description}")
            return "\n".join(lines)

        # Show specific skill details
        skill_id = args.strip()
        try:
            skill = session.shared_context.skill_loader.load_skill(skill_id)
        except Exception:
            return f"✗ Skill `{skill_id}` not found."

        lines = [
            f"**Skill:** `{skill.id}`",
            f"**Name:** {skill.name}",
            f"**Description:** {skill.description}",
            f"\n---\n\n**SKILL.md:**\n```\n{skill.content}\n```",
        ]
        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/commands/handlers.py tests/core/commands/test_handlers.py
git commit -m "feat: add detail view to /skills command"
```

---

### Task 3: Update CronsCommand for detail view

**Files:**
- Modify: `src/picklebot/core/commands/handlers.py:148-162`
- Modify: `tests/core/commands/test_handlers.py:139-145`

**Step 1: Write the failing tests**

Add tests in `tests/core/commands/test_handlers.py`:

```python
def test_crons_show_detail(self, mock_session, mock_context):
    """Test crons command shows detail for specific cron."""
    from picklebot.core.cron_loader import CronDef

    mock_cron = CronDef(
        id="daily-summary",
        name="Daily Summary",
        schedule="0 9 * * *",
        agent="pickle",
        content="Generate a daily summary of activities.",
    )
    mock_session.shared_context = mock_context
    mock_context.cron_loader.load.return_value = mock_cron

    cmd = CronsCommand()
    result = cmd.execute("daily-summary", mock_session)

    assert "**Cron:** `daily-summary`" in result
    assert "**Name:** Daily Summary" in result
    assert "**Schedule:** `0 9 * * *`" in result
    assert "**Agent:** pickle" in result
    assert "Generate a daily summary" in result
    mock_context.cron_loader.load.assert_called_once_with("daily-summary")

def test_crons_show_detail_not_found(self, mock_session, mock_context):
    """Test crons command handles non-existent cron."""
    mock_session.shared_context = mock_context
    mock_context.cron_loader.load.side_effect = ValueError("not found")

    cmd = CronsCommand()
    result = cmd.execute("nonexistent", mock_session)

    assert "not found" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute::test_crons_show_detail -v`
Expected: FAIL

**Step 3: Update CronsCommand**

In `src/picklebot/core/commands/handlers.py`:

```python
class CronsCommand(Command):
    """List all cron jobs or show cron details."""

    name = "crons"
    description = "List all cron jobs or show cron details"

    def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            crons = session.shared_context.cron_loader.discover_crons()
            if not crons:
                return "No cron jobs configured."

            lines = ["**Cron Jobs:**"]
            for cron in crons:
                lines.append(f"- `{cron.id}`: {cron.schedule}")
            return "\n".join(lines)

        # Show specific cron details
        cron_id = args.strip()
        try:
            cron = session.shared_context.cron_loader.load(cron_id)
        except Exception:
            return f"✗ Cron `{cron_id}` not found."

        lines = [
            f"**Cron:** `{cron.id}`",
            f"**Name:** {cron.name}",
            f"**Schedule:** `{cron.schedule}`",
            f"**Agent:** {cron.agent}",
            f"\n---\n\n**CRON.md:**\n```\n{cron.content}\n```",
        ]
        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestCommandExecute -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/commands/handlers.py tests/core/commands/test_handlers.py
git commit -m "feat: add detail view to /crons command"
```

---

### Task 4: Add RouteCommand

**Files:**
- Modify: `src/picklebot/core/commands/handlers.py`
- Modify: `src/picklebot/core/routing.py`
- Modify: `tests/core/commands/test_handlers.py`

**Step 1: Write the failing tests**

Add tests in `tests/core/commands/test_handlers.py`:

```python
class TestRouteCommand:
    """Tests for RouteCommand."""

    def test_route_creates_binding(self, mock_session, mock_context):
        """Test route command creates a binding."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.return_value = MagicMock()
        mock_context.config.routing = {"bindings": []}
        mock_context.config.sources = {}

        cmd = RouteCommand()
        result = cmd.execute("platform-telegram:.* pickle", mock_session)

        assert "✓ Route bound" in result
        assert "platform-telegram:.*" in result
        assert "pickle" in result

    def test_route_missing_args(self, mock_session, mock_context):
        """Test route command with missing args."""
        mock_session.shared_context = mock_context

        cmd = RouteCommand()
        result = cmd.execute("", mock_session)

        assert "Usage:" in result

    def test_route_agent_not_found(self, mock_session, mock_context):
        """Test route command with invalid agent."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.side_effect = ValueError("not found")

        cmd = RouteCommand()
        result = cmd.execute("platform-telegram:.* nonexistent", mock_session)

        assert "not found" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestRouteCommand -v`
Expected: FAIL - RouteCommand not defined

**Step 3: Add persist_binding method to RoutingTable**

In `src/picklebot/core/routing.py`, add to `RoutingTable` class:

```python
def persist_binding(self, source_pattern: str, agent_id: str) -> None:
    """
    Add and persist a routing binding to config.user.yaml.

    Args:
        source_pattern: Source pattern to match
        agent_id: Agent to route to
    """
    # Get existing bindings from user config
    bindings = self._context.config.routing.get("bindings", [])

    # Add new binding
    bindings.append({"agent": agent_id, "value": source_pattern})

    # Persist to config.user.yaml
    self._context.config.set_user("routing.bindings", bindings)

    # Clear cache to force reload
    self._bindings = None
```

**Step 4: Add RouteCommand**

In `src/picklebot/core/commands/handlers.py`, add:

```python
class RouteCommand(Command):
    """Create a routing binding."""

    name = "route"
    description = "Create a routing binding (persists to config)"

    def execute(self, args: str, session: "AgentSession") -> str:
        parts = args.strip().split(None, 1)
        if len(parts) != 2:
            return "**Usage:** `/route <source_pattern> <agent_id>`\n\nExample: `/route platform-telegram:.* pickle`"

        pattern, agent_id = parts

        # Verify agent exists
        try:
            session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        # Create and persist binding
        session.shared_context.routing_table.persist_binding(pattern, agent_id)

        return f"✓ Route bound: `{pattern}` → `{agent_id}`"
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestRouteCommand -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/commands/handlers.py src/picklebot/core/routing.py tests/core/commands/test_handlers.py
git commit -m "feat: add /route command for creating routing bindings"
```

---

### Task 5: Add BindingsCommand

**Files:**
- Modify: `src/picklebot/core/commands/handlers.py`
- Modify: `tests/core/commands/test_handlers.py`

**Step 1: Write the failing tests**

Add tests in `tests/core/commands/test_handlers.py`:

```python
class TestBindingsCommand:
    """Tests for BindingsCommand."""

    def test_bindings_shows_all(self, mock_session, mock_context):
        """Test bindings command shows all bindings."""
        mock_session.shared_context = mock_context
        mock_context.config.routing = {
            "bindings": [
                {"agent": "pickle", "value": "platform-telegram:.*"},
                {"agent": "cookie", "value": "platform-discord:.*"},
            ]
        }

        cmd = BindingsCommand()
        result = cmd.execute("", mock_session)

        assert "**Routing Bindings:**" in result
        assert "platform-telegram:.*" in result
        assert "pickle" in result
        assert "platform-discord:.*" in result
        assert "cookie" in result

    def test_bindings_empty(self, mock_session, mock_context):
        """Test bindings command with no bindings."""
        mock_session.shared_context = mock_context
        mock_context.config.routing = {"bindings": []}

        cmd = BindingsCommand()
        result = cmd.execute("", mock_session)

        assert "No routing bindings configured" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestBindingsCommand -v`
Expected: FAIL - BindingsCommand not defined

**Step 3: Add BindingsCommand**

In `src/picklebot/core/commands/handlers.py`, add:

```python
class BindingsCommand(Command):
    """Show all routing bindings."""

    name = "bindings"
    description = "Show all routing bindings"

    def execute(self, args: str, session: "AgentSession") -> str:
        bindings = session.shared_context.config.routing.get("bindings", [])

        if not bindings:
            return "No routing bindings configured."

        lines = ["**Routing Bindings:**"]
        for binding in bindings:
            lines.append(f"- `{binding['value']}` → `{binding['agent']}`")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/test_handlers.py::TestBindingsCommand -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/commands/handlers.py tests/core/commands/test_handlers.py
git commit -m "feat: add /bindings command to show routing bindings"
```

---

### Task 6: Register new commands and update registry test

**Files:**
- Modify: `src/picklebot/core/commands/registry.py:82-104`
- Modify: `tests/core/commands/test_registry.py:79-94`

**Step 1: Write the failing test**

Update `tests/core/commands/test_registry.py`:

```python
def test_with_builtins_has_all_commands(self):
    """Test with_builtins creates registry with builtin commands."""
    registry = CommandRegistry.with_builtins()

    # Should have all 10 commands (8 original + route + bindings)
    names = {cmd.name for cmd in registry.list_commands()}
    assert names == {
        "help",
        "agent",
        "skills",
        "crons",
        "compact",
        "context",
        "clear",
        "session",
        "route",
        "bindings",
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/commands/test_registry.py::TestCommandRegistryWithBuiltins::test_with_builtins_has_all_commands -v`
Expected: FAIL - missing route and bindings

**Step 3: Update registry.py**

In `src/picklebot/core/commands/registry.py`, update `with_builtins`:

```python
@classmethod
def with_builtins(cls) -> "CommandRegistry":
    """Create registry with built-in commands registered."""
    from picklebot.core.commands.handlers import (
        HelpCommand,
        AgentCommand,
        SkillsCommand,
        CronsCommand,
        CompactCommand,
        ContextCommand,
        ClearCommand,
        SessionCommand,
        RouteCommand,
        BindingsCommand,
    )

    registry = cls()
    registry.register(HelpCommand())
    registry.register(AgentCommand())
    registry.register(SkillsCommand())
    registry.register(CronsCommand())
    registry.register(CompactCommand())
    registry.register(ContextCommand())
    registry.register(ClearCommand())
    registry.register(SessionCommand())
    registry.register(RouteCommand())
    registry.register(BindingsCommand())
    return registry
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/commands/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/commands/registry.py tests/core/commands/test_registry.py
git commit -m "feat: register /route and /bindings commands"
```

---

### Task 7: Update docs

**Files:**
- Modify: `docs/features.md:160-188`

**Step 1: Update features.md**

Replace the Slash Commands section:

```markdown
## Slash Commands

Commands for managing conversations and agents. All commands start with `/`.

**Available Commands:**

| Command | Description |
|---------|-------------|
| `/help` or `/?` | Show available commands |
| `/agent [<id>]` | List agents or show agent details |
| `/skills [<id>]` | List skills or show skill details |
| `/crons [<id>]` | List cron jobs or show cron details |
| `/bindings` | Show all routing bindings |
| `/route <pattern> <agent_id>` | Create a routing binding (persists) |
| `/compact` | Trigger manual context compaction |
| `/context` | Show session context information |
| `/clear` | Clear conversation and start fresh |
| `/session` | Show current session details |

**Examples:**

```bash
# List all agents
/agent

# Show specific agent details
/agent pickle

# Create a routing binding
/route platform-telegram:.* pickle

# View all bindings
/bindings

# Clear conversation
/clear
```
```

**Step 2: Commit**

```bash
git add docs/features.md
git commit -m "docs: update features with new slash commands"
```

---

### Task 8: Final verification

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Manual test**

Run: `uv run picklebot chat`
Test each command:
- `/agent` - lists agents
- `/agent pickle` - shows pickle details
- `/skills` - lists skills
- `/skills <id>` - shows skill details
- `/crons` - lists crons
- `/crons <id>` - shows cron details
- `/bindings` - shows bindings
- `/route platform-cli:.* pickle` - creates binding
- `/bindings` - shows new binding
