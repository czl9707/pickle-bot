"""FastAPI dependencies for API routers."""

from fastapi import Request

from picklebot.core.context import SharedContext


def get_context(request: Request) -> SharedContext:
    """Get SharedContext from app state."""
    return request.app.state.context
