"""FastAPI application factory."""

from fastapi import FastAPI

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

    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(skills.router, prefix="/skills", tags=["skills"])
    app.include_router(crons.router, prefix="/crons", tags=["crons"])
    app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    app.include_router(memories.router, prefix="/memories", tags=["memories"])
    app.include_router(config.router, prefix="/config", tags=["config"])

    return app
