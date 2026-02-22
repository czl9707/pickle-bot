# Per-User Session Persistence for MessageBus

**Date:** 2026-02-22

## Overview

Each user on each platform gets their own session that persists across service restarts.

Currently, `MessageBusWorker` creates a single global session shared by all users. This design changes it to per-user sessions with persistence via runtime config.

## Goals

- Sessions keyed by `platform + user_id`
- Session IDs persisted in `config.runtime.yaml`
- Sessions resume on service restart
- Graceful recovery if session history is missing

## Changes

### 1. Config Model (`utils/config.py`)

Add `sessions` field to `TelegramConfig` and `DiscordConfig`:

```python
class TelegramConfig(BaseModel):
    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None
    sessions: dict[str, str] = Field(default_factory=dict)  # user_id -> session_id


class DiscordConfig(BaseModel):
    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None
    sessions: dict[str, str] = Field(default_factory=dict)  # user_id -> session_id
```

### 2. Agent Session Creation (`core/agent.py`)

Add optional `session_id` parameter to `new_session()`:

```python
def new_session(self, mode: SessionMode, session_id: str | None = None) -> "AgentSession":
    """
    Create a new conversation session.

    Args:
        mode: Session mode (CHAT or JOB)
        session_id: Optional session_id to use (for recovery scenarios)

    Returns:
        A new Session instance with mode-appropriate tools.
    """
    session_id = session_id or str(uuid.uuid4())
    # ... rest of method uses session_id
```

### 3. MessageBusWorker (`server/messagebus_worker.py`)

Replace global session with per-user session management:

```python
class MessageBusWorker(Worker):
    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue
        self.buses = context.messagebus_buses
        self.bus_map = {bus.platform_name: bus for bus in self.buses}

        # Load agent for session creation
        try:
            self.agent_def = context.agent_loader.load(context.config.default_agent)
            self.agent = Agent(self.agent_def, context)
        except DefNotFoundError as e:
            self.logger.error(f"Default agent not found: {context.config.default_agent}")
            raise RuntimeError(f"Failed to initialize MessageBusWorker: {e}") from e

    def _get_or_create_session_id(self, platform: str, user_id: str) -> str:
        """Get existing session_id or create new session for this user."""
        platform_config = getattr(self.context.config.messagebus, platform, None)
        if not platform_config:
            raise ValueError(f"No config for platform: {platform}")

        session_id = platform_config.sessions.get(user_id)

        if session_id:
            return session_id

        # No session - create new (creates in HistoryStore)
        session = self.agent.new_session(SessionMode.CHAT)

        # Persist session_id to runtime config
        self.context.config.set_runtime(
            f"messagebus.{platform}.sessions.{user_id}",
            session.session_id
        )

        return session.session_id

    def _create_callback(self, platform: str):
        async def callback(message: str, context: Any) -> None:
            try:
                bus = self.bus_map[platform]

                if not bus.is_allowed(context):
                    self.logger.debug(f"Ignored non-whitelisted message from {platform}")
                    return

                session_id = self._get_or_create_session_id(platform, context.user_id)
                frontend = MessageBusFrontend(bus, context)

                job = Job(
                    session_id=session_id,
                    agent_id=self.agent_def.id,
                    message=message,
                    frontend=frontend,
                    mode=SessionMode.CHAT,
                )
                await self.agent_queue.put(job)
            except Exception as e:
                self.logger.error(f"Error processing message from {platform}: {e}")

        return callback
```

### 4. AgentWorker (`server/agent_worker.py`)

Add fallback to `new_session()` if `resume_session()` fails:

```python
async def _process_job(self, job: Job) -> None:
    """Execute a single job with crash recovery."""
    try:
        agent_def = self.context.agent_loader.load(job.agent_id)
        agent = Agent(agent_def, self.context)

        if job.session_id:
            try:
                session = agent.resume_session(job.session_id)
            except ValueError:
                # Session not found in history - create new with same ID
                self.logger.warning(f"Session {job.session_id} not found, creating new")
                session = agent.new_session(job.mode, session_id=job.session_id)
        else:
            session = agent.new_session(job.mode)
            job.session_id = session.session_id

        await session.chat(job.message, job.frontend)
        self.logger.info(f"Job completed: session={job.session_id}")

    except DefNotFoundError as e:
        self.logger.error(f"Agent not found: {job.agent_id}: {e}")
    except Exception as e:
        self.logger.error(f"Job failed: {e}")
        job.message = "."
        await self.agent_queue.put(job)
```

## Config Structure

**config.user.yaml** (unchanged):
```yaml
messagebus:
  telegram:
    allowed_user_ids:
      - "123456"
      - "789012"
```

**config.runtime.yaml** (new sessions key):
```yaml
messagebus:
  telegram:
    sessions:
      "123456": "550e8400-e29b-41d4-a716-446655440000"
      "789012": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
  discord:
    sessions:
      "111222": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
```

## Flow

**On message:**
1. Check if user is in `allowed_user_ids` (existing behavior)
2. Look up session_id in `config.messagebus.{platform}.sessions[user_id]`
3. If found → return session_id
4. If not found → call `agent.new_session()`, persist session_id to runtime config
5. Create Job with session_id, put on agent_queue
6. AgentWorker resumes session, or creates new with same ID if missing from history

## Edge Cases

| Case | Behavior |
|------|----------|
| User not in allowed_user_ids | Message ignored (existing) |
| Session in config but not history | AgentWorker creates new with same session_id |
| Config write fails | Session still created, new session_id generated on next restart |
| Concurrent messages from same user | Possible duplicate sessions, last wins in config (rare, acceptable) |
