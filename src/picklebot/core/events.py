"""Event types and data classes for the event bus."""

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
    """Platform-agnostic event."""

    type: EventType
    session_id: str
    content: str
    source: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        return cls(
            type=EventType(data["type"]),
            session_id=data["session_id"],
            content=data["content"],
            source=data["source"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class InboundEvent:
    """Event for external work entering the system (platforms, cron, retry)."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    retry_count: int = 0
    context: MessageContext | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.INBOUND

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": "inbound",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "context": _serialize_context(self.context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboundEvent":
        """Deserialize event from dictionary."""
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            retry_count=data.get("retry_count", 0),
            context=_deserialize_context(data.get("context")),
        )


@dataclass
class OutboundEvent:
    """Event for agent responses to deliver to platforms."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.OUTBOUND

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": "outbound",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutboundEvent":
        """Deserialize event from dictionary."""
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            error=data.get("error"),
        )


@dataclass
class DispatchEvent:
    """Event for internal agent-to-agent delegation."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    parent_session_id: str
    retry_count: int = 0

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": "dispatch",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "parent_session_id": self.parent_session_id,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispatchEvent":
        """Deserialize event from dictionary."""
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            parent_session_id=data["parent_session_id"],
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class DispatchResultEvent:
    """Event for result of a dispatched job."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH_RESULT

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": "dispatch_result",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispatchResultEvent":
        """Deserialize event from dictionary."""
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            error=data.get("error"),
        )


# Type alias for all event types
TypedEvent = InboundEvent | OutboundEvent | DispatchEvent | DispatchResultEvent


def serialize_event(event: TypedEvent) -> dict[str, Any]:
    """Serialize any event type to dict."""
    return event.to_dict()


def deserialize_event(data: dict[str, Any]) -> TypedEvent:
    """Deserialize dict to appropriate event type."""
    event_type = data.get("type")

    if event_type == EventType.INBOUND.value:
        return InboundEvent.from_dict(data)
    elif event_type == EventType.OUTBOUND.value:
        return OutboundEvent.from_dict(data)
    elif event_type == EventType.DISPATCH.value:
        return DispatchEvent.from_dict(data)
    elif event_type == EventType.DISPATCH_RESULT.value:
        return DispatchResultEvent.from_dict(data)
    else:
        raise ValueError(f"Unknown event type: {event_type}")
