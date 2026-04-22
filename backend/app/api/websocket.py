import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket connected — %d active", len(self._connections))

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)
        logger.info("WebSocket disconnected — %d active", len(self._connections))

    async def broadcast(self, data: dict[str, Any]):
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, api_key: str | None = None):
    """Authenticated WebSocket endpoint.

    Auth is via `?api_key=` since browser WebSocket APIs can't set custom
    headers. If the server has no key configured we refuse the connection
    (matches the HTTP behaviour in `deps.require_api_key`).
    """
    settings = get_settings()
    if not settings.API_KEY:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if api_key != settings.API_KEY:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_json({"type": "ack", "message": data})
    except WebSocketDisconnect:
        manager.disconnect(ws)
