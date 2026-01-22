"""
WebSocket Routes for Real-Time Data
Provides live price feeds and trading updates.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging

from ..services.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/prices/{token_address}")
async def websocket_price_feed(
    websocket: WebSocket,
    token_address: str
):
    """
    WebSocket endpoint for real-time price updates.

    Connect to this endpoint to receive live price updates for a specific token.

    Args:
        token_address: Solana token mint address to subscribe to

    Example:
        ws://localhost:8000/api/v1/ws/prices/So11111111111111111111111111111111111111112

    Message Format:
        {
            "token_address": "So11111111111111111111111111111111111111112",
            "price": 125.42,
            "volume_24h": 2450000000,
            "price_change_24h": 5.32,
            "source": "aggregated",
            "timestamp": "2026-01-22T10:30:00Z"
        }
    """
    manager = get_websocket_manager()

    await manager.connect(websocket, token_address)

    try:
        while True:
            # Keep connection alive
            # Actual price updates are broadcast by the manager's background task
            data = await websocket.receive_text()

            # Client can send "ping" to check connection
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, token_address)
        logger.info(f"Client disconnected from {token_address[:8]}...")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, token_address)


@router.websocket("/portfolio")
async def websocket_portfolio_feed(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for portfolio updates.

    Real-time updates on user's portfolio value, positions, and P&L.

    Args:
        user_id: Optional user ID for authenticated feed

    Example:
        ws://localhost:8000/api/v1/ws/portfolio?user_id=123

    Message Format:
        {
            "type": "portfolio_update",
            "total_value_usd": 10500.50,
            "total_pnl_24h": 250.00,
            "total_pnl_pct_24h": 2.43,
            "positions": [
                {
                    "token": "SOL",
                    "amount": 10.5,
                    "value_usd": 1314.91,
                    "pnl_usd": 50.00,
                    "pnl_pct": 3.95
                }
            ],
            "timestamp": "2026-01-22T10:30:00Z"
        }
    """
    await websocket.accept()

    try:
        # TODO: Implement portfolio tracking
        # For now, send a placeholder message
        await websocket.send_json({
            "type": "portfolio_update",
            "message": "Portfolio tracking coming soon",
            "status": "beta"
        })

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Portfolio feed disconnected")
    except Exception as e:
        logger.error(f"Portfolio WebSocket error: {e}")


@router.websocket("/market")
async def websocket_market_feed(websocket: WebSocket):
    """
    WebSocket endpoint for general market updates.

    Broadcasts market-wide events, trending tokens, and alerts.

    Example:
        ws://localhost:8000/api/v1/ws/market

    Message Types:
        - trending_token: New trending token detected
        - high_volume: Unusual volume spike
        - ai_signal: AI recommendation for popular token
        - market_alert: Important market event
    """
    await websocket.accept()

    try:
        # TODO: Implement market feed
        await websocket.send_json({
            "type": "market_update",
            "message": "Market feed coming soon",
            "status": "beta"
        })

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Market feed disconnected")
    except Exception as e:
        logger.error(f"Market WebSocket error: {e}")
