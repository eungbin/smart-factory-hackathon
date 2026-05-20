from __future__ import annotations

from typing import Any, Protocol


class JsonWebSocket(Protocol):
    async def accept(self) -> None: ...

    async def send_json(self, data: Any) -> None: ...


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: set[JsonWebSocket] = set()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: JsonWebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: JsonWebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        stale_connections: list[JsonWebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(websocket)
