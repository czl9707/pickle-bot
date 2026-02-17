# Post Message Tool Design

## Overview

Add a tool that allows agents to proactively send messages to users via the message bus. This enables cron jobs and long-running tasks to notify users without requiring an incoming message first.

## Config Changes

Add per-platform fields to `messagebus` config in `utils/config.py`:

```yaml
messagebus:
  enabled: true
  default_platform: telegram
  telegram:
    enabled: true
    bot_token: "your-token"
    allowed_user_ids: ["123456789"]  # Whitelist for incoming messages
    default_user_id: "123456789"      # Target for outgoing messages
  discord:
    enabled: false
    bot_token: "your-token"
    channel_id: "optional-id"
    allowed_user_ids: []
    default_user_id: ""
```

### New Fields

- `allowed_user_ids: list[str]` — Whitelist of user IDs permitted to send messages to the bot
- `default_user_id: str` — Target user ID for agent-initiated messages

## MessageBus Changes

### Base Class (`messagebus/base.py`)

Make `user_id` optional on `send_message`:

```python
@abstractmethod
async def send_message(self, content: str, user_id: str = None) -> None:
    """
    Send message to user on this platform.

    Args:
        content: Message content to send
        user_id: Platform-specific user identifier (uses default if not provided)
    """
```

### Platform Implementations

Each implementation (TelegramBus, DiscordBus) falls back to `self.config.default_user_id` when `user_id` is `None`.

## Whitelist Enforcement

In `MessageBusExecutor._enqueue_message`, check whitelist before processing:

```python
async def _enqueue_message(self, message: str, platform: str, user_id: str) -> None:
    bus = self.bus_map[platform]
    if user_id not in bus.config.allowed_user_ids:
        logger.info(f"Ignored message from non-whitelisted user {platform}/{user_id}")
        return
    await self.message_queue.put((message, platform, user_id))
```

Non-whitelisted messages are silently ignored (logged but no response sent).

## Post Message Tool

### Tool Interface

```python
post_message(content: str) -> str
```

- `content`: Message to send
- Returns: Success confirmation or error message

### Registration

Tool is only registered when messagebus is enabled with valid config. Follows the same pattern as `create_skill_tool()` and `create_subagent_dispatch_tool()`:

- Factory function `create_post_message_tool(context: SharedContext) -> Optional[BaseTool]`
- Returns `None` if messagebus not configured, so tool is not added to registry

### Implementation

```python
async def post_message(content: str) -> str:
    # 1. Get default_platform from config
    # 2. Find bus in context.buses by platform name
    # 3. Call bus.send_message(content) (uses default_user_id)
    # 4. Return success/error message
```

## Files to Modify

1. `src/picklebot/utils/config.py` — Add `allowed_user_ids` and `default_user_id` to platform configs
2. `src/picklebot/messagebus/base.py` — Make `user_id` optional in `send_message`
3. `src/picklebot/messagebus/telegram_bus.py` — Implement fallback to `default_user_id`
4. `src/picklebot/messagebus/discord_bus.py` — Implement fallback to `default_user_id`
5. `src/picklebot/core/messagebus_executor.py` — Add whitelist check in `_enqueue_message`
6. `src/picklebot/tools/post_message_tool.py` — New file with tool factory
7. `src/picklebot/tools/registry.py` — Register tool via factory (or wherever tool registration happens)
