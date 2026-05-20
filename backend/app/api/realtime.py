from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.manager import RealtimeManager


router = APIRouter(prefix="/api/v1", tags=["realtime"])
realtime_manager = RealtimeManager()


@router.websocket("/realtime")
async def realtime_websocket(websocket: WebSocket) -> None:
    await realtime_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
