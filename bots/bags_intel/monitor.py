"""Monitor for bags.fm token graduations via Bitquery WebSocket."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional, Set

import aiohttp
import websockets
from websockets.client import WebSocketClientProtocol

from .config import BagsIntelConfig

logger = logging.getLogger("jarvis.bags_intel.monitor")

# GraphQL subscription for Meteora DBC migrations (graduations)
GRADUATION_SUBSCRIPTION = """
subscription BagsGraduations {
  Solana {
    Instructions(
      where: {
        Instruction: {
          Program: {
            Address: { is: "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN" }
            Method: { in: ["migrate_meteora_damm", "migration_damm_v2"] }
          }
        }
      }
    ) {
      Block {
        Time
        Slot
      }
      Transaction {
        Signature
        Signer
      }
      Instruction {
        Program {
          Method
        }
        Accounts {
          Address
          IsWritable
          Token {
            Mint
            Owner
          }
        }
      }
    }
  }
}
"""


class GraduationMonitor:
    """Monitor bags.fm for token graduations via Bitquery WebSocket."""

    def __init__(
        self,
        config: BagsIntelConfig,
        on_graduation: Optional[Callable] = None,
    ):
        self.config = config
        self.on_graduation = on_graduation
        self._running = False
        self._ws: Optional[WebSocketClientProtocol] = None
        self._processed_mints: Set[str] = set()
        self._reconnect_delay = 5

    async def connect(self) -> WebSocketClientProtocol:
        """Connect to Bitquery WebSocket."""
        if not self.config.bitquery_api_key:
            raise ValueError("BITQUERY_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {self.config.bitquery_api_key}",
            "Content-Type": "application/json",
        }

        ws = await websockets.connect(
            self.config.bitquery_ws_url,
            additional_headers=headers,
            subprotocols=["graphql-ws"],
            ping_interval=30,
            ping_timeout=10,
        )

        # Init connection
        await ws.send(json.dumps({"type": "connection_init", "payload": {}}))
        response = await ws.recv()
        data = json.loads(response)

        if data.get("type") != "connection_ack":
            raise ConnectionError(f"Connection not acknowledged: {data}")

        logger.info("Connected to Bitquery WebSocket")
        return ws

    async def subscribe(self, ws: WebSocketClientProtocol) -> None:
        """Subscribe to graduation events."""
        await ws.send(
            json.dumps({
                "id": "graduations",
                "type": "subscribe",
                "payload": {"query": GRADUATION_SUBSCRIPTION},
            })
        )
        logger.info("Subscribed to bags.fm graduations")

    async def _process_message(self, message: str) -> None:
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "next" and "payload" in data:
                await self._handle_graduation_event(data["payload"])
            elif msg_type == "error":
                logger.error(f"Bitquery error: {data.get('payload')}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def _handle_graduation_event(self, payload: dict) -> None:
        """Handle graduation event from Bitquery."""
        try:
            instructions = (
                payload.get("data", {}).get("Solana", {}).get("Instructions", [])
            )

            for instr in instructions:
                block = instr.get("Block", {})
                tx = instr.get("Transaction", {})
                accounts = instr.get("Instruction", {}).get("Accounts", [])

                # Find token mint
                token_mint = None
                for acc in accounts:
                    token_info = acc.get("Token")
                    if token_info and token_info.get("Mint"):
                        token_mint = token_info["Mint"]
                        break

                if not token_mint or token_mint in self._processed_mints:
                    continue

                self._processed_mints.add(token_mint)

                event = {
                    "mint_address": token_mint,
                    "signature": tx.get("Signature"),
                    "creator": tx.get("Signer"),
                    "timestamp": block.get("Time"),
                    "slot": block.get("Slot"),
                }

                logger.info(f"Graduation detected: {token_mint[:8]}...")

                if self.on_graduation:
                    await self.on_graduation(event)

        except Exception as e:
            logger.error(f"Graduation handling error: {e}")

    async def run(self) -> None:
        """Run monitor with auto-reconnect."""
        self._running = True

        while self._running:
            try:
                self._ws = await self.connect()
                await self.subscribe(self._ws)

                async for message in self._ws:
                    if not self._running:
                        break
                    await self._process_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket closed: {e.code} {e.reason}")
            except Exception as e:
                logger.error(f"Monitor error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)

    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Graduation monitor stopped")


class PollingFallback:
    """Fallback polling when WebSocket unavailable."""

    def __init__(
        self,
        config: BagsIntelConfig,
        on_graduation: Optional[Callable] = None,
        poll_interval: int = 30,
    ):
        self.config = config
        self.on_graduation = on_graduation
        self.poll_interval = poll_interval
        self._running = False
        self._last_checked: Set[str] = set()

    async def run(self) -> None:
        """Poll for new graduations."""
        self._running = True
        logger.info("Starting graduation polling fallback")

        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    await self._poll_dexscreener(session)
                except Exception as e:
                    logger.error(f"Polling error: {e}")

                await asyncio.sleep(self.poll_interval)

    async def _poll_dexscreener(self, session: aiohttp.ClientSession) -> None:
        """Poll DexScreener for new Meteora pairs."""
        # This is a simplified fallback - checks for new pairs
        url = "https://api.dexscreener.com/latest/dex/search?q=meteora"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                pairs = data.get("pairs", [])

                for pair in pairs[:20]:  # Check recent pairs
                    mint = pair.get("baseToken", {}).get("address")
                    if not mint or mint in self._last_checked:
                        continue

                    # Check if it's a bags.fm token (heuristic)
                    created = pair.get("pairCreatedAt", 0)
                    if created > 0:
                        age_minutes = (datetime.utcnow().timestamp() * 1000 - created) / 60000
                        if age_minutes < 60:  # New in last hour
                            self._last_checked.add(mint)

                            if self.on_graduation:
                                await self.on_graduation({
                                    "mint_address": mint,
                                    "signature": None,
                                    "creator": None,
                                    "timestamp": datetime.utcnow().isoformat(),
                                })

        except Exception as e:
            logger.debug(f"DexScreener poll error: {e}")

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        logger.info("Polling fallback stopped")
