"""Event types and data classes for the event bus."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageContext


class EventSource(ABC):
    """Abstract base for all event sources.

    Subclasses define _namespace for registry lookup and implement
    serialization via __str__ and from_string.
    """

    _registry: ClassVar[dict[str, type["EventSource"]]] = {}
    _namespace: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls._namespace:
            cls._registry[cls._namespace] = cls

    @property
    def is_platform(self) -> bool:
        return self._namespace.startswith("platform-")

    @property
    def is_agent(self) -> bool:
        return self._namespace == "agent"

    @property
    def is_cron(self) -> bool:
        return self._namespace == "cron"

    @property
    def platform_name(self) -> str | None:
        if not self.is_platform:
            return None
        return self._namespace.split("-", 1)[1]

    @classmethod
    def from_string(cls, s: str) -> "EventSource":
        """Parse string to EventSource using namespace registry."""
        namespace = s.split(":")[0]
        source_cls = cls._registry.get(namespace)
        if not source_cls:
            raise ValueError(f"Unknown source namespace: {namespace}")
        return source_cls.from_string(s)

    @abstractmethod
    def __str__(self) -> str: ...


@dataclass
class AgentEventSource(EventSource):
    """Source for agent-generated events."""

    _namespace = "agent"
    agent_id: str

    def __str__(self) -> str:
        return f"agent:{self.agent_id}"

    @classmethod
    def from_string(cls, s: str) -> "AgentEventSource":
        _, agent_id = s.split(":", 1)
        return cls(agent_id=agent_id)


@dataclass
class CronEventSource(EventSource):
    """Source for cron-triggered events."""

    _namespace = "cron"
    cron_id: str

    def __str__(self) -> str:
        return f"cron:{self.cron_id}"

    @classmethod
    def from_string(cls, s: str) -> "CronEventSource":
        _, cron_id = s.split(":", 1)
        return cls(cron_id=cron_id)


class Source:
    """Factory for creating typed event sources.

    Source format: "<type>:<identifier>" or just "<type>" for system sources.

    Examples:
        Source.agent("pickle")       -> "agent:pickle"
        Source.platform("telegram", "user_123") -> "telegram:user_123"
    """

    @staticmethod
    def agent(agent_id: str) -> str:
        """Create source for agent-generated events."""
        return f"agent:{agent_id}"

    @staticmethod
    def platform(platform: str, user_id: str) -> str:
        """Create source for platform-originated events."""
        return f"{platform}:{user_id}"

    @staticmethod
    def cron(cron_id: str) -> str:
        """Create source for cron-triggered events."""
        return f"cron:{cron_id}"


def _serialize_context(context: "MessageContext | None") -> dict[str, Any]:
    """Serialize a MessageContext to a dictionary."""
    if context is None:
        return {}

    # Get the class name to identify the context type
    context_type = type(context).__name__

    # Extract dataclass fields if it's a dataclass
    if hasattr(context, "__dataclass_fields__"):
        data = {}
        for field_name in context.__dataclass_fields__:
            data[field_name] = getattr(context, field_name)
        return {"type": context_type, "data": data}

    return {"type": context_type, "data": {}}


def _deserialize_context(data: dict[str, Any] | None) -> "MessageContext | None":
    """Deserialize a dictionary back to a MessageContext."""
    if not data:
        return None

    context_type = data.get("type")
    context_data = data.get("data", {})

    # Import here to avoid circular imports
    if context_type == "TelegramContext":
        from picklebot.messagebus.telegram_bus import TelegramContext

        return TelegramContext(**context_data)
    elif context_type == "DiscordContext":
        from picklebot.messagebus.discord_bus import DiscordContext

        return DiscordContext(**context_data)
    elif context_type == "CliContext":
        from picklebot.messagebus.cli_bus import CliContext

        return CliContext(**context_data)

    return None


@dataclass
class Event:
    """Base class for all typed events.

    Subclasses define additional fields specific to that event type.
    Event type is determined by the class name for serialization.
    """

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary, including type."""
        result: dict[str, Any] = {"type": self.__class__.__name__}
        # Add all dataclass fields
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name == "context":
                result[field_name] = _serialize_context(value)
            else:
                result[field_name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary, excluding type field."""
        # Filter out 'type' - it's determined by the class, not constructor
        # Also filter to only include fields that this dataclass expects
        kwargs = {}
        for k, v in data.items():
            if k == "type":
                continue
            if k == "context":
                kwargs[k] = _deserialize_context(v)
            elif k in cls.__dataclass_fields__:
                kwargs[k] = v

        return cls(**kwargs)


@dataclass
class InboundEvent(Event):
    """Event for external work entering the system (platforms, cron, retry)."""

    retry_count: int = 0
    context: "MessageContext | None" = None


@dataclass
class OutboundEvent(Event):
    """Event for agent responses to deliver to platforms."""

    error: str | None = None


@dataclass
class DispatchEvent(Event):
    """Event for internal agent-to-agent delegation."""

    parent_session_id: str = ""
    retry_count: int = 0


@dataclass
class DispatchResultEvent(Event):
    """Event for result of a dispatched job."""

    error: str | None = None


# Registry mapping event class names to event classes
_EVENT_CLASSES: dict[str, type[Event]] = {
    "InboundEvent": InboundEvent,
    "OutboundEvent": OutboundEvent,
    "DispatchEvent": DispatchEvent,
    "DispatchResultEvent": DispatchResultEvent,
}


def serialize_event(event: Event) -> dict[str, Any]:
    """Serialize any event type to dict."""
    return event.to_dict()


def deserialize_event(data: dict[str, Any]) -> Event:
    """Deserialize dict to appropriate event type."""
    event_type: str = data.get("type")

    event_class = _EVENT_CLASSES.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_class.from_dict(data)
