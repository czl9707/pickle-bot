# WebSocket Gateway Design

Add real-time bidirectional WebSocket to existing FastAPI for external integrations.

## Architecture

```
External Client (web UI, IDE plugin)
        │
        ▼ ws://localhost:8000/ws
┌─────────────────┐
│   FastAPI App   │  (existing api/app.py)
│  ┌───────────┐  │
│  │ REST API  │  │  ← existing routers
│  └───────────┘  │
│  ┌───────────┐  │
│  │  /ws      │  │  ← new WebSocket endpoint
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
   SharedContext
         │
         ▼
   Agent.chat()
```

## JSON-RPC 2.0 Methods

| Method | Params | Returns |
|--------|--------|---------|
| `send` | `{text, channel?, peer_id?}` | `{agent_id, session_key, reply}` |
| `bindings.list` | — | `[{agent_id, match_key, match_value}]` |
| `agents.list` | — | `[{id, name}]` |
| `sessions.list` | `{agent_id?}` | `{session_key: msg_count}` |
| `status` | — | `{uptime, clients, agents}` |

## Key Interfaces

```python
# api/routers/gateway.py

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ctx: SharedContext = Depends(get_context)
):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            response = await handle_rpc(data, ctx)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass

async def handle_rpc(request: dict, ctx: SharedContext) -> dict:
    """Dispatch JSON-RPC method, return response or error."""
```

## Server-to-Client Notifications

```python
# Broadcast typing indicator to all connected clients
async def broadcast_typing(agent_id: str, typing: bool):
    message = {"jsonrpc": "2.0", "method": "typing", "params": {...}}
    for ws in connected_clients:
        await ws.send_json(message)
```

## Config

```yaml
gateway:
  enabled: true
  path: "/ws"  # WebSocket path on existing API server
```

## Integration Points

- **Location:** New router `api/routers/gateway.py`
- **Usage:** Mount in `api/app.py` alongside existing routers
- **Connection Management:** Track connected clients for broadcasts

## References

- claw0 s05_gateway_routing.py: `GatewayServer` class
