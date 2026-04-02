"""
Treasury WebSocket Handler
Prompt #86: Treasury Transparency Dashboard - Real-time updates

Provides real-time treasury data via WebSocket.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import json

logger = logging.getLogger("jarvis.treasury.websocket")


# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class TreasuryWebSocketManager:
    """Manages WebSocket connections for treasury updates"""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._update_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"Treasury WebSocket connected. Total: {len(self._connections)}")

        # Send initial state
        try:
            initial = await self._get_treasury_state()
            await websocket.send_json(initial)
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self._connections.discard(websocket)
        logger.info(f"Treasury WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected clients"""
        if not self._connections:
            return

        disconnected = []
        for websocket in self._connections:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            self._connections.discard(ws)

    async def start_updates(self, interval: float = 5.0):
        """Start broadcasting updates at interval"""
        if self._running:
            return

        self._running = True
        self._update_task = asyncio.create_task(
            self._update_loop(interval)
        )
        logger.info("Treasury WebSocket updates started")

    async def stop_updates(self):
        """Stop the update loop"""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        logger.info("Treasury WebSocket updates stopped")

    async def _update_loop(self, interval: float):
        """Background task to push updates"""
        while self._running:
            try:
                if self._connections:
                    data = await self._get_treasury_state()
                    await self.broadcast(data)
            except Exception as e:
                logger.error(f"Treasury update error: {e}")

            await asyncio.sleep(interval)

    async def _get_treasury_state(self) -> Dict[str, Any]:
        """Get current treasury state"""
        try:
            from core.treasury import get_treasury

            treasury = get_treasury()
            status = await treasury.get_status()
            pnl = treasury.get_pnl_report()

            return {
                "type": "treasury_update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "wallets": status.get("wallets", {}),
                    "risk": status.get("risk", {}),
                    "running": status.get("running", False),
                    "pnl": pnl,
                }
            }
        except Exception as e:
            logger.error(f"Error getting treasury state: {e}")
            return {
                "type": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

_manager: Optional[TreasuryWebSocketManager] = None


def get_treasury_ws_manager() -> TreasuryWebSocketManager:
    """Get or create the WebSocket manager"""
    global _manager
    if _manager is None:
        _manager = TreasuryWebSocketManager()
    return _manager


async def treasury_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for treasury updates"""
    manager = get_treasury_ws_manager()

    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                elif message.get("type") == "subscribe":
                    # Client can subscribe to specific updates
                    pass

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# =============================================================================
# ROUTER
# =============================================================================

def create_treasury_ws_router():
    """Create WebSocket router for treasury"""
    from fastapi import APIRouter

    router = APIRouter()

    @router.websocket("/ws/treasury")
    async def websocket_route(websocket: WebSocket):
        await treasury_websocket_endpoint(websocket)

    return router
