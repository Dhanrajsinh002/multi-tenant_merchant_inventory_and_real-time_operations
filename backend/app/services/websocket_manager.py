import logging
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketEventType(str, Enum):
    STOCK_UPDATED = "STOCK_UPDATED"
    APPROVAL_CREATED = "APPROVAL_CREATED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    LOW_STOCK_ALERT = "LOW_STOCK_ALERT"


class WebSocketManager:
    """
    Manages active WebSocket connections grouped into tenant-specific rooms.
    Ensures tenant isolation and supports echo-back exclusion.
    """

    def __init__(self):
        # Structure: { merchant_id: { connection_id: WebSocket } }
        self._rooms: Dict[int, Dict[str, WebSocket]] = {}

    def _get_room_name(self, merchant_id: int) -> str:
        return f"room:merchant_{merchant_id}"

    async def connect(self, merchant_id: int, websocket: WebSocket) -> str:
        """Accept websocket connection and register it in the tenant room."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        
        if merchant_id not in self._rooms:
            self._rooms[merchant_id] = {}
        self._rooms[merchant_id][connection_id] = websocket
        
        logger.info(f"Client {connection_id} joined {self._get_room_name(merchant_id)}. Room size: {len(self._rooms[merchant_id])}")
        return connection_id

    def disconnect(self, merchant_id: int, connection_id: str) -> None:
        """Remove disconnected socket from the tenant room."""
        if merchant_id in self._rooms and connection_id in self._rooms[merchant_id]:
            del self._rooms[merchant_id][connection_id]
            logger.info(f"Client {connection_id} left {self._get_room_name(merchant_id)}.")
            if not self._rooms[merchant_id]:
                del self._rooms[merchant_id]

    async def broadcast_to_merchant(
        self,
        merchant_id: int,
        event_type: WebSocketEventType,
        data: Any,
        exclude_connection_id: Optional[str] = None
    ) -> None:
        """
        Broadcast a JSON event strictly to the tenant's room.
        Optionally excludes the originating connection to prevent echo-back.
        """
        if merchant_id not in self._rooms:
            return

        message = {
            "event": event_type.value,
            "merchant_id": merchant_id,
            "data": data,
        }

        dead_connections = []
        for conn_id, socket in list(self._rooms[merchant_id].items()):
            if exclude_connection_id and conn_id == exclude_connection_id:
                continue  # Skip originator to prevent echo-back
            try:
                await socket.send_json(message)
            except Exception as exc:
                logger.warning(f"Failed sending to socket {conn_id}: {exc}")
                dead_connections.append(conn_id)

        # Clean up any sockets that disconnected unexpectedly
        for conn_id in dead_connections:
            self.disconnect(merchant_id, conn_id)


# Global singleton instance
ws_manager = WebSocketManager()