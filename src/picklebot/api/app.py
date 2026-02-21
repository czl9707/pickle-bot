"""FastAPI application factory."""

from fastapi import FastAPI

from picklebot.core.context import SharedContext


def create_app(context: SharedContext) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    # Routers will be added here as they are created
    # app.include_router(agents.router, prefix="/agents", tags=["agents"])
    # ...

    return app
