"""WebSocket optimization utilities."""
import asyncio
import json
import time
import gzip
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MessageBatch:
    """Batch of messages for efficient delivery."""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    
    def add(self, message: Dict[str, Any]):
        self.messages.append(message)
    
    def is_ready(self, max_size: int = 10, max_age_ms: float = 100) -> bool:
        if len(self.messages) >= max_size:
            return True
        if (time.time() - self.created_at) * 1000 >= max_age_ms:
            return True
        return False
    
    def get_payload(self) -> bytes:
        return json.dumps({"batch": self.messages}).encode()


class WebSocketOptimizer:
    """Optimize WebSocket message delivery."""
    
    def __init__(
        self,
        batch_size: int = 10,
        batch_delay_ms: float = 50,
        compression_threshold: int = 1024,
        heartbeat_interval: float = 30.0
    ):
        self.batch_size = batch_size
        self.batch_delay_ms = batch_delay_ms
        self.compression_threshold = compression_threshold
        self.heartbeat_interval = heartbeat_interval
        
        self._batches: Dict[str, MessageBatch] = {}
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._last_heartbeat: Dict[str, float] = {}
        self._message_dedup: Dict[str, float] = {}
        self._dedup_ttl = 5.0  # seconds
    
    def should_compress(self, data: bytes) -> bool:
        """Check if data should be compressed."""
        return len(data) > self.compression_threshold
    
    def compress(self, data: bytes) -> bytes:
        """Compress data using gzip."""
        return gzip.compress(data, compresslevel=6)
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress gzip data."""
        return gzip.decompress(data)
    
    def add_to_batch(self, channel: str, message: Dict[str, Any]) -> Optional[bytes]:
        """Add message to batch, return payload if batch is ready."""
        if channel not in self._batches:
            self._batches[channel] = MessageBatch()
        
        batch = self._batches[channel]
        batch.add(message)
        
        if batch.is_ready(self.batch_size, self.batch_delay_ms):
            payload = batch.get_payload()
            self._batches[channel] = MessageBatch()
            
            if self.should_compress(payload):
                return self.compress(payload)
            return payload
        
        return None
    
    async def flush_batch(self, channel: str) -> Optional[bytes]:
        """Force flush a batch."""
        if channel in self._batches and self._batches[channel].messages:
            batch = self._batches[channel]
            payload = batch.get_payload()
            self._batches[channel] = MessageBatch()
            return payload
        return None
    
    def is_duplicate(self, message_id: str) -> bool:
        """Check if message is a duplicate."""
        now = time.time()
        
        # Clean old entries
        self._message_dedup = {
            k: v for k, v in self._message_dedup.items()
            if now - v < self._dedup_ttl
        }
        
        if message_id in self._message_dedup:
            return True
        
        self._message_dedup[message_id] = now
        return False
    
    def needs_heartbeat(self, client_id: str) -> bool:
        """Check if client needs a heartbeat."""
        now = time.time()
        last = self._last_heartbeat.get(client_id, 0)
        
        if now - last >= self.heartbeat_interval:
            self._last_heartbeat[client_id] = now
            return True
        return False
    
    def get_heartbeat_message(self) -> Dict[str, Any]:
        """Generate heartbeat message."""
        return {
            "type": "heartbeat",
            "timestamp": time.time(),
            "server_time": int(time.time() * 1000)
        }
    
    def subscribe(self, client_id: str, channel: str):
        """Subscribe client to channel."""
        self._subscriptions[channel].add(client_id)
    
    def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe client from channel."""
        self._subscriptions[channel].discard(client_id)
    
    def unsubscribe_all(self, client_id: str):
        """Unsubscribe client from all channels."""
        for channel in self._subscriptions:
            self._subscriptions[channel].discard(client_id)
        self._last_heartbeat.pop(client_id, None)
    
    def get_subscribers(self, channel: str) -> Set[str]:
        """Get subscribers for a channel."""
        return self._subscriptions.get(channel, set())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        return {
            "active_channels": len(self._subscriptions),
            "total_subscribers": sum(len(s) for s in self._subscriptions.values()),
            "pending_batches": sum(len(b.messages) for b in self._batches.values()),
            "dedup_cache_size": len(self._message_dedup)
        }


class RateLimitedBroadcast:
    """Rate-limited broadcasting for high-frequency updates."""
    
    def __init__(self, min_interval_ms: float = 100):
        self.min_interval_ms = min_interval_ms
        self._last_broadcast: Dict[str, float] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
    
    async def broadcast(
        self,
        channel: str,
        message: Dict[str, Any],
        send_func
    ) -> bool:
        """Broadcast with rate limiting, returns True if sent."""
        now = time.time() * 1000
        last = self._last_broadcast.get(channel, 0)
        
        if now - last >= self.min_interval_ms:
            self._last_broadcast[channel] = now
            await send_func(channel, message)
            return True
        else:
            # Store for later
            self._pending[channel] = message
            return False
    
    async def flush_pending(self, send_func):
        """Send all pending messages."""
        for channel, message in list(self._pending.items()):
            await send_func(channel, message)
        self._pending.clear()


# Global optimizer instance
ws_optimizer = WebSocketOptimizer()
