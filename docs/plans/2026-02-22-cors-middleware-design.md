# CORS Middleware Design

## Problem

API requests from browsers fail due to CORS preflight failures. The FastAPI app does not have CORS middleware configured, so OPTIONS requests are not handled.

## Solution

Add Starlette's `CORSMiddleware` to the FastAPI application in `create_app()`.

## Implementation

**File:** `src/picklebot/api/app.py`

```python
from fastapi.middleware.cors import CORSMiddleware

def create_app(context: SharedContext) -> FastAPI:
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    # CORS middleware for browser requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # routers...
```

## Configuration

Hardcoded permissive defaults for now:
- `allow_origins=["*"]` — Accept requests from any origin
- `allow_methods=["*"]` — Allow all HTTP methods
- `allow_headers=["*"]` — Allow all headers

Can be made configurable via `config.user.yaml` in the future if needed.

## Scope

- Single file change
- ~5 lines of code
