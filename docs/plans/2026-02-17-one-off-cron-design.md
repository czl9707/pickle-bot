# One-Off Cron Jobs Design

## Problem

Cron jobs currently run indefinitely on their schedule. There's no way to create a task that runs once and then automatically cleans itself up.

## Solution

Add an optional `one_off` field to cron definitions. When `one_off: true`, the server deletes the cron file and folder after successful execution.

## Changes

### 1. CronDef Model (`src/picklebot/core/cron_loader.py`)

Add optional `one_off` field:

```python
class CronDef(BaseModel):
    """Loaded cron job definition."""

    id: str
    name: str
    agent: str
    schedule: str
    prompt: str
    one_off: bool = False  # NEW: auto-delete after successful execution
```

### 2. CronLoader (`src/picklebot/core/cron_loader.py`)

Parse `one_off` from frontmatter in both parsing methods:

```python
return CronDef(
    id=def_id,
    name=frontmatter.get("name"),
    agent=frontmatter.get("agent"),
    schedule=frontmatter.get("schedule"),
    prompt=body.strip(),
    one_off=frontmatter.get("one_off", False),  # NEW
)
```

### 3. CronExecutor (`src/picklebot/core/cron_executor.py`)

After successful execution, delete the cron folder if `one_off=True`:

```python
async def _run_job(self, cron_def: CronDef) -> None:
    try:
        agent_def = self.context.agent_loader.load(cron_def.agent)
        agent = Agent(agent_def, self.context)
        session = agent.new_session()
        await session.chat(cron_def.prompt, SilentFrontend())

        logger.info(f"Cron job {cron_def.id} completed successfully")

        # NEW: Delete one-off crons after successful execution
        if cron_def.one_off:
            cron_path = self.context.cron_loader.crons_path / cron_def.id
            shutil.rmtree(cron_path)
            logger.info(f"Deleted one-off cron job: {cron_def.id}")

    except Exception as e:
        logger.error(f"Error executing cron job {cron_def.id}: {e}")
        raise
```

### 4. Cron-Ops Skill (`~/.pickle-bot/skills/cron-ops/SKILL.md`)

Add guidance to clarify one-off vs recurring:

- Add `one_off: true` to validation rules section
- Add clarification step in create command
- Add example showing one-off usage

### 5. CLAUDE.md

Document the `one_off` field in the Cron System section with example and behavior notes.

## Behavior

- **Schedule format:** Standard cron syntax (5 fields)
- **Deletion timing:** Only after successful execution
- **Failed jobs:** Keep the file for retry on next tick
- **Default:** `one_off: false` (recurring), fully backward compatible

## Example

```yaml
---
name: Birthday Reminder
agent: pickle
schedule: "0 9 15 3 *"
one_off: true
---

Remind me it's Mom's birthday today.
```
