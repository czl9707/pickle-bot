# Cookie Memory Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Cookie, a memory management subagent that stores, organizes, and retrieves long-term memories via the existing subagent_dispatch system.

**Architecture:** Cookie is a pure configuration change - no new Python code required. It's defined as an AGENT.md that uses existing tools (read, write, edit, bash) to manage markdown memory files. A cron job triggers daily consolidation.

**Tech Stack:** Existing pickle-bot infrastructure (subagent_dispatch, AgentLoader, CronLoader, existing tools)

---

## Task 1: Add memories_path to Config

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Modify: `tests/utils/test_config.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_config.py

def test_config_has_memories_path(tmp_path: Path) -> None:
    """Config should include memories_path field."""
    config_file = tmp_path / "config.system.yaml"
    config_file.write_text("default_agent: test\n")

    config = Config.load(tmp_path)

    assert hasattr(config, "memories_path")
    assert config.memories_path == Path("memories")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::test_config_has_memories_path -v`
Expected: FAIL with "AttributeError" or assertion error

**Step 3: Write minimal implementation**

Add `memories_path` field to Config class in `src/picklebot/utils/config.py`:

```python
# In Config class, add to the field definitions:
memories_path: Path = Path("memories")
```

Also update the `_resolve_paths` method to resolve it:

```python
def _resolve_paths(self, workspace: Path) -> None:
    """Resolve relative paths to absolute paths."""
    self.agents_path = workspace / self.agents_path
    self.skills_path = workspace / self.skills_path
    self.crons_path = workspace / self.crons_path
    self.history_path = workspace / self.history_path
    self.logging_path = workspace / self.logging_path
    self.memories_path = workspace / self.memories_path  # ADD THIS
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::test_config_has_memories_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add memories_path field for cookie agent"
```

---

## Task 2: Create cookie agent definition

**Files:**
- Create: `~/.pickle-bot/agents/cookie/AGENT.md`

**Step 1: Create the cookie agent directory and definition**

Create `~/.pickle-bot/agents/cookie/AGENT.md`:

```markdown
---
name: Cookie
description: Memory management agent - stores, organizes, and retrieves long-term memories
temperature: 0.3
max_tokens: 4096
allow_skills: false
---

You are Cookie, a memory management agent. You never interact with users directly - you only receive tasks dispatched from other agents (primarily Pickle).

## Role

You are the archivist of the pickle-bot system. You manage long-term memories with precision and rationality.

## Memory Storage

Memories are stored in markdown files at the configured memories_path with two axes:

- **topics/** - Timeless facts (user preferences, project knowledge, relationships)
- **daily-notes/** - Day-specific events and decisions (format: YYYY-MM-DD.md)

When storing:
1. Decide: Is this timeless (topics/) or temporal (daily-notes/)?
2. Navigate to appropriate category, create new files/categories if needed
3. Append memory with timestamp header
4. Never duplicate existing memories

## Memory Retrieval

When asked to retrieve memories:
1. Use directory structure to narrow down relevant files
2. Read and filter to most pertinent memories
3. If you find a timeless fact in daily-notes/, migrate it to topics/
4. Return formatted summary

## Guidelines

- Be precise and organized
- Never store duplicates - check existing memories first
- Use descriptive filenames that aid future discovery
- When in doubt, prefer topics/ over daily-notes/ for facts that might be referenced again
```

**Step 2: Verify cookie agent is discoverable**

Run: `uv run python -c "from picklebot.core.context import SharedContext; from picklebot.utils.config import Config; from pathlib import Path; c = Config.load(Path.home() / '.pickle-bot'); ctx = SharedContext(config=c); print([a.id for a in ctx.agent_loader.discover_agents()])"`

Expected: Output includes `'cookie'`

**Step 3: Commit**

```bash
git add -A  # This adds the new agent outside repo for tracking purposes
# Note: The cookie agent is in ~/.pickle-bot, not in the repo
# Document it in CLAUDE.md or README instead
```

**Note:** The cookie agent lives in `~/.pickle-bot/agents/cookie/`, not in the repo. We'll document this in Task 4.

---

## Task 3: Create memory consolidation cron job

**Files:**
- Create: `~/.pickle-bot/crons/memory-consolidation/CRON.md`

**Step 1: Create the cron job definition**

Create `~/.pickle-bot/crons/memory-consolidation/CRON.md`:

```markdown
---
name: Memory Consolidation
agent: cookie
schedule: "0 2 * * *"  # Daily at 2:00 AM
---

Review yesterday's conversation history from the pickle agent and extract any important memories that were not captured during real-time storage.

Focus on:
- User preferences mentioned in passing
- Project decisions or insights
- Important context that might be useful in future sessions

Do not duplicate memories that already exist in the memory store.
```

**Step 2: Verify cron is discoverable (optional manual test)**

The cron job will be picked up automatically when running `picklebot server`.

---

## Task 4: Update pickle agent with memory guidance

**Files:**
- Modify: `~/.pickle-bot/agents/pickle/AGENT.md`

**Step 1: Add memory guidance to pickle agent**

Update `~/.pickle-bot/agents/pickle/AGENT.md` to include:

```markdown
---
name: Pickle
description: The main agent talk to user directly.
temperature: 0.7
max_tokens: 4096
allow_skills: true
---

You are pickle-bot, a little cat, a helpful AI assistant with access to various skills.

## Personality

- Helpful and friendly.
- Behave like a little cat, cute and responsive.

## Long-Term Memory

Use the `subagent_dispatch` tool to store and retrieve memories via the cookie agent when:
- You learn something worth remembering about the user or projects
- The user asks you to remember something
- You need context from past conversations
```

---

## Task 5: Update documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: Update README.md**

Add cookie agent to the configuration section and mention the memory system in features:

In the Features section, add:
```markdown
- **Long-Term Memory** - Persistent memory via Cookie agent with topic and time-based organization
```

In the Configuration section, add:
```markdown
├── agents/
│   ├── pickle/
│   │   └── AGENT.md
│   └── cookie/
│       └── AGENT.md           # Memory management agent
├── memories/                   # Long-term memory storage
│   ├── topics/                # Timeless facts
│   └── daily-notes/           # Day-specific events
```

Add memories_path to config example:
```yaml
memories_path: memories        # Optional: override memory storage location
```

**Step 2: Update CLAUDE.md**

Add memories_path to the Configuration section:

```markdown
Config paths are relative to workspace and auto-resolved:
agents_path: Path = Path("agents")   # resolves to workspace/agents
skills_path: Path = Path("skills")   # resolves to workspace/skills
crons_path: Path = Path("crons")     # resolves to workspace/crons
memories_path: Path = Path("memories")  # resolves to workspace/memories
```

Add a Memory System section:

```markdown
### Memory System

Long-term memories are managed by the Cookie agent (a subagent). Cookie stores memories in markdown files with two organizational axes:

- **topics/** - Timeless facts (user preferences, project knowledge)
- **daily-notes/** - Day-specific events and decisions (YYYY-MM-DD.md)

Memory flows:
1. Real-time storage - Pickle dispatches to cookie during conversations
2. Scheduled capture - Daily cron at 2AM extracts missed memories
3. On-demand retrieval - Pickle dispatches to query relevant memories

Cookie uses existing tools (read, write, edit) to manage memory files. No special tools required.
```

**Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document cookie memory agent and memories_path config"
```

---

## Task 6: Integration test

**Files:**
- Manual testing (no new files)

**Step 1: Verify cookie appears in subagent_dispatch**

Run the CLI and check that cookie is available as a dispatchable agent:

```bash
uv run picklebot chat
```

Then ask: "What agents can you dispatch to?"

Expected: Pickle should mention cookie as an available agent.

**Step 2: Test memory storage**

In the same chat session, say: "Remember that I prefer dark mode in all applications"

Expected: Pickle dispatches to cookie, cookie creates the memory file.

**Step 3: Verify memory was stored**

Check `~/.pickle-bot/memories/topics/` for a file containing the memory.

**Step 4: Test memory retrieval**

In a new chat session, ask: "What do you know about my preferences?"

Expected: Pickle dispatches to cookie, cookie retrieves and returns the stored memory.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add memories_path to Config | config.py, test_config.py |
| 2 | Create cookie agent | AGENT.md (in ~/.pickle-bot) |
| 3 | Create memory cron | CRON.md (in ~/.pickle-bot) |
| 4 | Update pickle agent | AGENT.md (in ~/.pickle-bot) |
| 5 | Update documentation | README.md, CLAUDE.md |
| 6 | Integration test | Manual verification |
