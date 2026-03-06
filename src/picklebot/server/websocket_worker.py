# src/picklebot/server/websocket_worker.py
"""WebSocket worker for broadcasting events to connected clients."""

import logging
import time
import dataclasses
from typing import TYPE_CHECKING, Set

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import ValidationError

from .worker import SubscriberWorker
from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    WebSocketEventSource,
)

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.api.schemas import WebSocketMessage

logger = logging.getLogger(__name__)


class WebSocketWorker(SubscriberWorker):
    """Manages WebSocket connections and event broadcasting.

    Subscribes to all EventBus events and broadcasts to connected WebSocket clients.
    Also handles incoming WebSocket messages, normalizes them to InboundEvents,
    and emits them to the EventBus.
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.clients: Set[WebSocket] = set()

        # Auto-subscribe to all event classes
        for event_class in [
            InboundEvent,
            OutboundEvent,
            DispatchEvent,
            DispatchResultEvent,
        ]:
            self.context.eventbus.subscribe(event_class, self.handle_event)
        self.logger.info("WebSocketWorker subscribed to all event types")

    async def handle_connection(self, ws: WebSocket) -> None:
        """Handle a single WebSocket connection lifecycle.

        Args:
            ws: WebSocket connection from FastAPI endpoint
        """
        self.clients.add(ws)
        self.logger.info(
            f"WebSocket client connected. Total clients: {len(self.clients)}"
        )

        try:
            # WebSocket should already be accepted by the endpoint
            # We don't need to call accept() again
            await self._run_client_loop(ws)
        finally:
            self.clients.discard(ws)
            self.logger.info(
                f"WebSocket client disconnected. Total clients: {len(self.clients)}"
            )

    async def _run_client_loop(self, ws: WebSocket) -> None:
        """Run message receiving loop for a single client.

        Continuously receives messages from client, validates them,
        normalizes to InboundEvent, and emits to EventBus.

        Args:
            ws: WebSocket connection
        """
        from picklebot.api.schemas import WebSocketMessage  # Avoid circular import

        while True:
            try:
                # Receive and validate message
                data = await ws.receive_json()
                msg = WebSocketMessage(**data)

                # Normalize to InboundEvent
                event = self._normalize_message(msg)

                # Emit to EventBus
                await self.context.eventbus.emit(event)
                self.logger.debug(f"Emitted InboundEvent from WebSocket: {msg.source}")

            except WebSocketDisconnect:
                self.logger.info("Client disconnected normally")
                break
            except ValidationError as e:
                # Send validation error back to client
                await ws.send_json(
                    {"type": "error", "message": f"Validation error: {e}"}
                )
                self.logger.warning(f"Validation error from client: {e}")
                # Don't disconnect - let client retry
            except Exception as e:
                self.logger.error(f"Unexpected error in client loop: {e}")
                break

    def _normalize_message(self, msg: "WebSocketMessage") -> InboundEvent:
        """Normalize WebSocketMessage to InboundEvent.

        Args:
            msg: Validated WebSocket message

        Returns:
            InboundEvent ready to emit to EventBus
        """
        # Determine agent_id (use routing if null)
        agent_id = msg.agent_id
        if agent_id is None:
            agent_id = self._route_message(msg.source, msg.content)

        # Lookup or create session
        session_id = self._get_or_create_session(agent_id, msg.source)

        return InboundEvent(
            session_id=session_id,
            agent_id=agent_id,
            source=WebSocketEventSource(user_id=msg.source),
            content=msg.content,
            timestamp=time.time(),
        )

    def _route_message(self, source: str, content: str) -> str:
        """Route message to determine target agent.

        Uses SharedContext routing to determine agent_id based on source.

        Args:
            source: Client source identifier
            content: Message content

        Returns:
            Agent ID to handle this message
        """
        # Use routing system to determine agent
        # For now, default to 'pickle' agent
        # TODO: Integrate with routing system when available
        return "pickle"

    def _get_or_create_session(self, agent_id: str, source: str) -> str:
        """Get existing session or create new one.

        Args:
            agent_id: Target agent ID
            source: Client source identifier

        Returns:
            Session ID
        """
        # For now, create a simple session ID based on source and agent
        # TODO: Integrate with proper session management
        import hashlib

        session_key = f"{agent_id}:{source}"
        return hashlib.md5(session_key.encode()).hexdigest()[:12]

    async def handle_event(self, event: Event) -> None:
        """Handle EventBus event by broadcasting to WebSocket clients.

        Args:
            event: Event from EventBus
        """
        if not self.clients:
            return

        # Serialize event to dict with type information
        event_dict = {
            "type": event.__class__.__name__,
        }
        event_dict.update(dataclasses.asdict(event))

        # Convert EventSource to string for JSON serialization
        if "source" in event_dict and hasattr(event.source, "__str__"):
            event_dict["source"] = str(event.source)

        # Broadcast to all clients
        self.logger.debug(
            f"Broadcasting {event.__class__.__name__} to {len(self.clients)} clients"
        )

        for client in list(self.clients):
            try:
                await client.send_json(event_dict)
            except Exception as e:
                self.logger.error(f"Failed to send to client: {e}")
                self.clients.discard(client)
