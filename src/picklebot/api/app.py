"""FastAPI application factory."""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from picklebot.api.routers import agents, config, crons, memories, sessions, skills
from picklebot.core.context import SharedContext


def create_app(context: SharedContext) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(skills.router, prefix="/skills", tags=["skills"])
    app.include_router(crons.router, prefix="/crons", tags=["crons"])
    app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    app.include_router(memories.router, prefix="/memories", tags=["memories"])
    app.include_router(config.router, prefix="/config", tags=["config"])

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time event streaming and chat.

        Clients can:
        - Receive all EventBus events in real-time
        - Send messages that create InboundEvents

        Message format (client -> server):
            {
                "source": "user-id",
                "content": "message text",
                "agent_id": "pickle"  # optional
            }

        Event format (server -> client):
            {
                "type": "InboundEvent",
                "session_id": "...",
                "agent_id": "...",
                "source": "platform-ws:user-id",
                "content": "...",
                ...
            }
        """
        await websocket.accept()

        # Check if WebSocket worker is available
        if context.websocket_worker is None:
            await websocket.close(code=1013, reason="WebSocket not available")
            return

        # Hand off to worker
        await context.websocket_worker.handle_connection(websocket)

    return app
