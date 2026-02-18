# MessageBus Context Refactor Design

## Problem

The current MessageBus implementation uses confusing naming and conflates different concepts:

1. `user_id` in the code is actually `chat_id` (Telegram) or `channel_id` (Discord)
2. `allowed_user_ids` whitelists by chat/channel, not by person (inconsistent with user expectation)
3. `default_user_id` is semantically about "where to post" not "who"
4. Discord's `allowed_user_ids` was configured but never implemented

## Solution

Refactor MessageBus to use platform-specific contexts with clear semantics:

- Whitelist by **person** (`user_id`) not chat/channel
- Reply to **where the message came from**
- Post to **configured destination** (`default_chat_id`)

## Config Changes

Rename `default_user_id` to `default_chat_id`:

| Field | Before | After |
|-------|--------|-------|
| TelegramConfig | `default_user_id` | `default_chat_id` |
| DiscordConfig | `default_user_id` | `default_chat_id` |
| Both | `allowed_user_ids` | (unchanged) |

## New MessageBus Interface

Generic interface with platform-specific context type:

```python
T = TypeVar("T")

class MessageBus(ABC, Generic[T]):
    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @abstractmethod
    async def start(self, on_message: Callable[[str, T], Awaitable[None]]) -> None:
        """Start listening. Calls on_message(content, context)."""

    @abstractmethod
    def is_allowed(self, context: T) -> bool:
        """Check if sender is whitelisted."""

    @abstractmethod
    async def reply(self, content: str, context: T) -> None:
        """Reply using the context from incoming message."""

    @abstractmethod
    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message to default_chat_id or specific target."""

    @abstractmethod
    async def stop(self) -> None: ...
```

## Platform Contexts

### TelegramContext

```python
@dataclass
class TelegramContext:
    user_id: str   # from_user.id - for whitelisting (the person)
    chat_id: str   # effective_chat.id - for replying (the conversation)
```

### DiscordContext

```python
@dataclass
class DiscordContext:
    user_id: str     # author.id - for whitelisting (the person)
    channel_id: str  # channel.id - for replying (the channel)
```

## Behavior by Platform

### Telegram

| Method | Source/Target |
|--------|---------------|
| Whitelist | `context.user_id` from `update.message.from_user.id` |
| Reply | `context.chat_id` from `update.effective_chat.id` |
| Post | `config.default_chat_id` |

### Discord

| Method | Source/Target |
|--------|---------------|
| Whitelist | `context.user_id` from `message.author.id` |
| Reply | `context.channel_id` from `message.channel.id` |
| Post | `config.default_chat_id` |

## MessageBusExecutor Changes

The executor stores platform-specific context and delegates to bus methods:

```python
# Queue stores (content, platform, context) - context is platform-specific
self.message_queue: asyncio.Queue[tuple[str, str, Any]] = asyncio.Queue()

async def _enqueue_message(self, message: str, platform: str, context: Any) -> None:
    bus = self.bus_map[platform]

    # Delegate whitelist check to bus
    if not bus.is_allowed(context):
        logger.info(f"Ignored message from non-whitelisted user on {platform}")
        return

    await self.message_queue.put((message, platform, context))

async def _process_messages(self) -> None:
    while True:
        message, platform, context = await self.message_queue.get()
        bus = self.bus_map[platform]

        response = await self.session.chat(message, self.frontend)
        await bus.reply(content=response, context=context)  # Use reply() with context
```

## Files to Change

1. `src/picklebot/utils/config.py` - Rename `default_user_id` to `default_chat_id`
2. `src/picklebot/messagebus/base.py` - New generic interface with context
3. `src/picklebot/messagebus/telegram_bus.py` - Implement with TelegramContext
4. `src/picklebot/messagebus/discord_bus.py` - Implement with DiscordContext
5. `src/picklebot/core/messagebus_executor.py` - Update to use new interface
6. `src/picklebot/tools/post_message_tool.py` - Use `post()` instead of `send_message()`

## Backward Compatibility

This is a breaking config change. Users will need to update their `config.user.yaml`:

```yaml
# Before
messagebus:
  telegram:
    default_user_id: "123456789"

# After
messagebus:
  telegram:
    default_chat_id: "123456789"
```

## Future Extensions

The `post()` method accepts an optional `target` parameter for future expansion:
- `target="user:123"` - DM specific user
- `target="channel:456"` - Post to specific channel

Discord could later support DM-style replies by extending `DiscordContext` and `reply()` implementation.
