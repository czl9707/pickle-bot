from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
