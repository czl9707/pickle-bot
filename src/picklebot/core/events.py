"""Event types and data classes for the event bus."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from picklebot.messagebus.base import MessageContext


class EventType(str, Enum):
    """Types of events in the system."""

    INBOUND = "inbound"  # External work entering the system (platforms, cron, retry)
    OUTBOUND = "outbound"  # Agent responses to deliver to platforms
    STATUS = "status"  # Status updates
    DISPATCH = "dispatch"  # Internal agent-to-agent delegation
    DISPATCH_RESULT = "dispatch_result"  # Result of a dispatched job


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

    @staticmethod
    def retry() -> str:
        """Create source for retry events."""
        return "retry"


def _serialize_context(context: MessageContext | None) -> dict[str, Any] | None:
    """Serialize a MessageContext to a dictionary."""
    if context is None:
        return None

    # Get the class name to identify the context type
    context_type = type(context).__name__

    # Extract dataclass fields if it's a dataclass
    if hasattr(context, "__dataclass_fields__"):
        data = {}
        for field_name in context.__dataclass_fields__:
            data[field_name] = getattr(context, field_name)
        return {"type": context_type, "data": data}

    return {"type": context_type, "data": {}}


def _deserialize_context(data: dict[str, Any] | None) -> MessageContext | None:
    """Deserialize a dictionary back to a MessageContext."""
    if data is None:
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

    Subclasses must define:
    - type property returning their EventType
    - Any additional fields specific to that event type
    """

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float = field(default_factory=time.time)

    @property
    def type(self) -> EventType:
        """Return the event type. Must be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement type property")

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary, including type."""
        result = {"type": self.type.value}
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
    context: MessageContext | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.INBOUND


@dataclass
class OutboundEvent(Event):
    """Event for agent responses to deliver to platforms."""

    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.OUTBOUND


@dataclass
class DispatchEvent(Event):
    """Event for internal agent-to-agent delegation."""

    parent_session_id: str = ""
    retry_count: int = 0

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH


@dataclass
class DispatchResultEvent(Event):
    """Event for result of a dispatched job."""

    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH_RESULT


# Registry mapping event type strings to event classes
_EVENT_CLASSES: dict[str, type[Event]] = {
    EventType.INBOUND.value: InboundEvent,
    EventType.OUTBOUND.value: OutboundEvent,
    EventType.DISPATCH.value: DispatchEvent,
    EventType.DISPATCH_RESULT.value: DispatchResultEvent,
}


def serialize_event(event: Event) -> dict[str, Any]:
    """Serialize any event type to dict."""
    return event.to_dict()


def deserialize_event(data: dict[str, Any]) -> Event:
    """Deserialize dict to appropriate event type."""
    event_type = data.get("type")

    event_class = _EVENT_CLASSES.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_class.from_dict(data)
