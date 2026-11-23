import logging
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from app.core.security import decode_access_token
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/merchant")
async def merchant_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Real-Time WebSocket endpoint authenticated via JWT query parameter.
    Assigns authenticated clients to room:merchant_{merchant_id}.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
        return

    payload = decode_access_token(token)
    if not payload or "merchant_id" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    merchant_id = int(payload["merchant_id"])
    connection_id = await ws_manager.connect(merchant_id, websocket)

    # Send initial handshake confirmation to the connected client
    try:
        await websocket.send_json({
            "event": "CONNECTED",
            "connection_id": connection_id,
            "room": f"room:merchant_{merchant_id}",
            "message": "Successfully connected to tenant real-time channel."
        })

        # Keep connection alive and listen for incoming heartbeats/ping
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(merchant_id, connection_id)
    except Exception as exc:
        logger.warning(f"WebSocket error on connection {connection_id}: {exc}")
        ws_manager.disconnect(merchant_id, connection_id)