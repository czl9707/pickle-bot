# Documentation Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh README.md, CLAUDE.md, and docs/ to reflect current codebase and separate user/developer content.

**Architecture:** Delete extending.md, move internal patterns from CLAUDE.md to architecture.md, restructure configuration.md as single YAML example, add web tools documentation throughout.

**Tech Stack:** Markdown, YAML examples

---

## Task 1: Delete docs/extending.md

**Files:**
- Delete: `docs/extending.md`

**Step 1: Delete the file**

```bash
rm docs/extending.md
```

**Step 2: Verify deletion**

```bash
ls docs/extending.md
```

Expected: "No such file or directory"

**Step 3: Commit**

```bash
git add -A
git commit -m "docs: remove extending.md (content merged into other docs)"
```

---

## Task 2: Update docs/architecture.md

**Files:**
- Modify: `docs/architecture.md`

**Step 1: Update Provider Architecture section**

Replace the LLMProvider section (around line 166-182) with expanded Provider Architecture section covering LLM, Web Search, and Web Read providers with correct paths.

Update paths:
- `provider/base.py` → `provider/llm/base.py`
- `provider/providers.py` → `provider/llm/providers.py`

Add new sections for:
- `provider/web_search/base.py` - WebSearchProvider, SearchResult
- `provider/web_read/base.py` - WebReadProvider, ReadResult

**Step 2: Add Definition Loading section (moved from CLAUDE.md)**

Add after Component Architecture:
```markdown
### def_loader (utils/def_loader.py)

Shared utilities for parsing markdown files with YAML frontmatter.

**Functions:**
- `parse_definition(path, model_class)` - Parse single definition
- `discover_definitions(path, model_class)` - Find all definitions in directory
- `write_definition(id, frontmatter, content, base_path, filename)` - Write definition with frontmatter

**Returns:** Pydantic model instance with frontmatter fields + markdown body

**Raises:**
- `DefNotFoundError` - Definition folder/file doesn't exist
- `InvalidDefError` - Definition file is malformed
```

**Step 3: Add Message Conversion section (moved from CLAUDE.md)**

Add after Definition Loading:
```markdown
### Message Conversion

`HistoryMessage` <-> litellm `Message` conversion for persistence and LLM context:

```python
from picklebot.core.history import HistoryMessage

# Message -> HistoryMessage (for persistence)
history_msg = HistoryMessage.from_message(message)

# HistoryMessage -> Message (for LLM context)
message = history_msg.to_message()
```

Bidirectional conversion ensures compatibility with all LLM providers via litellm.
```

**Step 4: Add Config Loading section (moved from CLAUDE.md)**

Add after Message Conversion:
```markdown
### Config Loading (utils/config.py)

Two-layer deep merge: `config.user.yaml` <- `config.runtime.yaml`

- **config.user.yaml** - User configuration (required fields: `llm`, `default_agent`). Created by onboarding.
- **config.runtime.yaml** - Runtime state (optional, internal only, managed by application)

**Programmatic updates:**

```python
# User preferences (persists to config.user.yaml)
ctx.config.set_user("default_agent", "cookie")

# Runtime state (persists to config.runtime.yaml)
ctx.config.set_runtime("current_session_id", "abc123")
```

**Deep merge:** Nested objects merge recursively; scalar values are replaced.
```

**Step 5: Add HTTP API Internals section (moved from CLAUDE.md)**

Add after Config Loading:
```markdown
### HTTP API Internals

FastAPI-based REST API using `SharedContext` via dependency injection:

```python
from picklebot.api.deps import get_context
from picklebot.core.context import SharedContext
from fastapi import Depends

@router.get("/{agent_id}")
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)):
    return ctx.agent_loader.load(agent_id)
```

**Creating definitions via API:**

```python
from picklebot.utils.def_loader import write_definition

frontmatter = {"name": "My Agent", "temperature": 0.7}
write_definition("my-agent", frontmatter, "System prompt...", agents_path, "AGENT.md")
```
```

**Step 6: Update Project Structure tree**

Replace the project structure tree (around line 340-381) with updated version including:
- `provider/llm/` (base.py, providers.py)
- `provider/web_search/` (base.py, brave.py)
- `provider/web_read/` (base.py, crawl4ai.py)
- `cli/onboarding/` (wizard.py, steps.py)

**Step 7: Verify file**

Review the updated file to ensure all sections are present and paths are correct.

**Step 8: Commit**

```bash
git add docs/architecture.md
git commit -m "docs(architecture): expand with provider sections and internal patterns"
```

---

## Task 3: Update docs/configuration.md

**Files:**
- Modify: `docs/configuration.md`

**Step 1: Restructure Configuration Options section**

Replace the split configuration options sections (LLM Settings, Path Configuration, etc.) with a single comprehensive YAML example.

**Step 2: Add Web Tools configuration**

Add websearch and webread sections to the YAML example:
```yaml
# Web Tools (optional)
websearch:
  provider: brave
  api_key: "your-brave-api-key"

webread:
  provider: crawl4ai
```

**Step 3: Remove programmatic methods section**

Remove the "Updating Config Programmatically" section with `set_user()`/`set_runtime()` examples (moved to architecture.md).

**Step 4: Add runtime-managed note to YAML example**

Add a section at the end of the YAML showing runtime-managed fields with a comment explaining they are auto-updated.

**Step 5: Verify file**

Review the updated file to ensure the YAML example is complete and all options are documented.

**Step 6: Commit**

```bash
git add docs/configuration.md
git commit -m "docs(configuration): restructure as single comprehensive YAML example"
```

---

## Task 4: Update docs/features.md

**Files:**
- Modify: `docs/features.md`

**Step 1: Add Web Tools section**

Add new section after Memory System:
```markdown
## Web Tools

Pickle-bot can search the web and read web pages when configured.

### Web Search

Search the web for information using the `websearch` tool.

**Configuration required:**
```yaml
websearch:
  provider: brave
  api_key: "your-brave-api-key"
```

**Usage:** The agent can call `websearch` to find information and return results with titles, URLs, and snippets.

### Web Read

Read and extract content from web pages using the `webread` tool.

**Configuration required:**
```yaml
webread:
  provider: crawl4ai
```

**Usage:** The agent can call `webread` to fetch a URL and return the content as markdown.

### Providers

- **Web Search:** Brave (requires API key)
- **Web Read:** Crawl4AI (no API key needed, uses local browser)
```

**Step 2: Simplify HTTP API section**

Remove implementation details (dependency injection, write_definition internals). Keep:
- Available endpoints table
- Example curl commands
- Link to architecture.md for internals

**Step 3: Remove loader internals from other sections**

In Agents, Skills, Crons sections, remove any internal loader details that are now in architecture.md.

**Step 4: Verify file**

Review the updated file to ensure web tools are documented and internals are removed.

**Step 5: Commit**

```bash
git add docs/features.md
git commit -m "docs(features): add web tools section, remove internals"
```

---

## Task 5: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Remove Critical Patterns section**

Delete the entire "Critical Patterns" section (Worker Architecture, Definition Loading, HTTP API, Message Conversion, Tool Registration, Config Loading, Nested LLM Config). These are now in architecture.md.

**Step 2: Simplify Key Files section**

Keep the list of key files but remove detailed descriptions. Just list paths with brief (3-5 word) descriptions.

**Step 3: Simplify Key Conventions**

Keep high-level conventions only:
- Workers use queues, single responsibility
- Sessions persist to disk
- Tools are async functions returning strings
- MessageBus is platform-agnostic

**Step 4: Update "What Goes Where"**

Ensure links point to correct docs. Add link to architecture.md for internal patterns.

**Step 5: Verify file**

Review CLAUDE.md - it should be concise (~80-100 lines) with just essential context.

**Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLADE.md): simplify, move internal patterns to architecture.md"
```

---

## Task 6: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Update tagline**

Refresh the description to be more compelling and accurate.

**Step 2: Add PyPI installation**

Add to Installation section:
```markdown
## Installation

```bash
# From PyPI
pip install pickle-bot

# Or from source
git clone https://github.com/zane-chen/pickle-bot.git
cd pickle-bot
uv sync
```
```

**Step 3: Update Quick Start**

Mention onboarding wizard:
```markdown
## Quick Start

```bash
picklebot init      # First run: interactive onboarding wizard
picklebot chat      # Start chatting with your AI assistant
```
```

**Step 4: Update Features list**

Add web tools to features:
```markdown
## Features

- **Multi-Agent AI** - Specialized agents with configurable LLM settings
- **Web Tools** - Search and read web content
- **Skills** - On-demand capability loading
- **Cron Jobs** - Scheduled automated tasks
- **Memory System** - Long-term context storage
- **Multi-Platform** - CLI, Telegram, Discord
- **HTTP API** - RESTful API for programmatic access
```

**Step 5: Verify file**

Review README.md - it should be concise and scannable.

**Step 6: Commit**

```bash
git add README.md
git commit -m "docs(README): add PyPI install, onboarding, web tools"
```

---

## Task 7: Final Review

**Step 1: Review all changed files**

```bash
git diff main --stat
```

**Step 2: Verify doc links work**

Check that all internal links between docs are valid.

**Step 3: Create summary commit if needed**

```bash
git log --oneline main..HEAD
```

**Step 4: Mark plan complete**

All documentation updated and committed.

---

## Summary

| Task | File | Action |
|------|------|--------|
| 1 | docs/extending.md | Delete |
| 2 | docs/architecture.md | Expand with providers, absorb patterns |
| 3 | docs/configuration.md | Restructure as single YAML |
| 4 | docs/features.md | Add web tools, remove internals |
| 5 | CLAUDE.md | Simplify, remove patterns |
| 6 | README.md | Add PyPI, onboarding, web tools |
| 7 | — | Final review |
