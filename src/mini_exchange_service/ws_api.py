"""WebSocket endpoint for real-time trades and top-of-book (service layer only)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def market_stream(websocket: WebSocket) -> None:
    hub = getattr(websocket.app.state, "hub", None)
    if hub is None:
        await websocket.close(code=4403)
        return
    await hub.run_session(websocket)
