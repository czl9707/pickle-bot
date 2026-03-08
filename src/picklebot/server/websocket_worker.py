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
                data = await ws.receive_json()
                msg = WebSocketMessage(**data)

                event = self._normalize_message(msg)

                await self.context.eventbus.publish(event)
                self.logger.debug(f"Emitted InboundEvent from WebSocket: {msg.source}")

            except WebSocketDisconnect:
                self.logger.info("Client disconnected normally")
                break
            except ValidationError as e:
                await ws.send_json(
                    {"type": "error", "message": f"Validation error: {e}"}
                )
                self.logger.warning(f"Validation error from client: {e}")
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
        source = WebSocketEventSource(user_id=msg.source)

        agent_id = msg.agent_id
        if agent_id is None:
            agent_id = self.context.routing_table.resolve(str(source))

        session_id = self.context.routing_table.get_or_create_session_id(
            source, agent_id
        )

        return InboundEvent(
            session_id=session_id,
            source=source,
            content=msg.content,
            timestamp=time.time(),
        )

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
