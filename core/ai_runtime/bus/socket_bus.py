"""
Local Unix Socket Message Bus

Secure inter-agent communication that never leaves the machine.
Uses HMAC signing for message authentication.
"""
import os
import json
import hmac
import hashlib
import socket
import asyncio
import logging
import sys
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import struct

from ..exceptions import BusException

logger = logging.getLogger(__name__)

# Check if Unix sockets are available (not on Windows)
HAS_UNIX_SOCKETS = hasattr(asyncio, 'start_unix_server')


@dataclass
class BusMessage:
    """Message format for inter-agent communication."""

    msg_id: str
    from_agent: str
    to_agent: str  # "supervisor" or specific agent or "broadcast"
    msg_type: str  # "insight", "request", "response", "error"
    payload: Dict[str, Any]
    timestamp: str
    signature: str = ""

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self)).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "BusMessage":
        return cls(**json.loads(data.decode("utf-8")))


class SecureMessageBus:
    """
    Unix domain socket bus with HMAC authentication.

    Why Unix sockets:
    - Local only (no network exposure)
    - Fast (no TCP overhead)
    - Permissions via filesystem
    - Easy to audit
    """

    def __init__(self, socket_path: str, hmac_key: Optional[str] = None):
        self.socket_path = socket_path
        self.hmac_key = (hmac_key or os.urandom(32).hex()).encode()
        self._handlers: Dict[str, Callable] = {}
        self._server: Optional[asyncio.Server] = None
        self._running = False

    def sign_message(self, msg: BusMessage) -> str:
        """Create HMAC signature for message authentication."""
        content = f"{msg.msg_id}:{msg.from_agent}:{msg.to_agent}:{msg.timestamp}"
        return hmac.new(self.hmac_key, content.encode(), hashlib.sha256).hexdigest()

    def verify_signature(self, msg: BusMessage) -> bool:
        """Verify message signature."""
        expected = self.sign_message(msg)
        return hmac.compare_digest(msg.signature, expected)

    async def start_server(self):
        """Start the message bus server."""
        # Check if Unix sockets are supported
        if not HAS_UNIX_SOCKETS:
            logger.warning(
                "Unix sockets not available on this platform (Windows). "
                "Message bus will not be started. Agents will operate independently."
            )
            self._running = False
            return

        try:
            # Remove existing socket
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)

            self._server = await asyncio.start_unix_server(
                self._handle_connection, path=self.socket_path
            )
            # Restrict permissions
            os.chmod(self.socket_path, 0o600)
            self._running = True
            logger.info(f"AI Bus started on {self.socket_path}")
        except Exception as e:
            logger.error(f"Failed to start bus server: {e}")
            raise BusException(f"Failed to start bus: {e}")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming connection."""
        try:
            # Read message length (4 bytes)
            length_data = await asyncio.wait_for(reader.read(4), timeout=5.0)
            if len(length_data) < 4:
                return
            msg_length = struct.unpack(">I", length_data)[0]

            # Sanity check
            if msg_length > 65536:
                logger.warning("Message too large, rejecting")
                return

            # Read message
            data = await asyncio.wait_for(reader.read(msg_length), timeout=5.0)
            msg = BusMessage.from_bytes(data)

            # Verify signature
            if not self.verify_signature(msg):
                logger.warning(f"Invalid signature from {msg.from_agent}")
                return

            # Route to handler
            if msg.to_agent in self._handlers:
                await self._handlers[msg.to_agent](msg)
            elif "broadcast" in self._handlers and msg.to_agent == "broadcast":
                await self._handlers["broadcast"](msg)

        except asyncio.TimeoutError:
            logger.debug("Connection timeout")
        except Exception as e:
            logger.error(f"Bus error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    def register_handler(self, agent_name: str, handler: Callable):
        """Register a message handler for an agent."""
        self._handlers[agent_name] = handler
        logger.debug(f"Registered handler for {agent_name}")

    async def send(self, msg: BusMessage) -> bool:
        """Send a message through the bus."""
        msg.signature = self.sign_message(msg)

        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            data = msg.to_bytes()

            # Send length + data
            writer.write(struct.pack(">I", len(data)))
            writer.write(data)
            await writer.drain()

            writer.close()
            await writer.wait_closed()
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def stop(self):
        """Stop the message bus."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception as e:
                logger.warning(f"Failed to remove socket: {e}")
        logger.info("AI Bus stopped")

    @property
    def is_running(self) -> bool:
        return self._running
