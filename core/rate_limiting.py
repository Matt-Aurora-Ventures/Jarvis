"""Rate limiting middleware for Telegram bot security.

Prevents API abuse and ensures fair usage across all users.
Implements per-user rate limiting with configurable time windows.

Usage:
    from core.rate_limiting import RateLimiter
    
    # In bot setup
    rate_limiter = RateLimiter(requests_per_minute=30)
    
    # In handler
    if not rate_limiter.check(user_id):
        await update.message.reply_text("Too many requests. Please wait.")
        return
"""

import time
import logging
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    burst_size: int = 5  # Allow short bursts


class RateLimiter:
    """Per-user rate limiting with multiple time windows.
    
    Tracks requests per user across different time windows to prevent:
    - Spam (30 req/min limit)
    - API abuse (500 req/hour limit)
    - Flash floods (5 req burst protection)
    """
    
    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        burst_size: int = 5
    ):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per user per minute
            requests_per_hour: Max requests per user per hour
            burst_size: Max requests in 5 second window
        """
        self.config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size
        )
        
        # Track request timestamps per user
        self.user_requests: Dict[int, list[float]] = defaultdict(list)
        
        # Track last cleanup time
        self.last_cleanup = time.time()
    
    def check(self, user_id: int) -> bool:
        """Check if user is within rate limits.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request allowed, False if rate limited
        """
        now = time.time()
        
        # Periodic cleanup of old timestamps
        if now - self.last_cleanup > 300:  # Every 5 minutes
            self._cleanup_old_requests()
        
        # Get user's request history
        requests = self.user_requests[user_id]
        
        # Remove timestamps older than 1 hour
        cutoff_hour = now - 3600
        requests = [ts for ts in requests if ts > cutoff_hour]
        self.user_requests[user_id] = requests
        
        # Check burst limit (last 5 seconds)
        cutoff_burst = now - 5
        burst_count = sum(1 for ts in requests if ts > cutoff_burst)
        if burst_count >= self.config.burst_size:
            logger.warning(
                f"User {user_id} exceeded burst limit: "
                f"{burst_count} requests in 5 seconds"
            )
            return False
        
        # Check per-minute limit
        cutoff_minute = now - 60
        minute_count = sum(1 for ts in requests if ts > cutoff_minute)
        if minute_count >= self.config.requests_per_minute:
            logger.warning(
                f"User {user_id} exceeded per-minute limit: "
                f"{minute_count} requests in 60 seconds"
            )
            return False
        
        # Check per-hour limit
        hour_count = len(requests)
        if hour_count >= self.config.requests_per_hour:
            logger.warning(
                f"User {user_id} exceeded per-hour limit: "
                f"{hour_count} requests in 1 hour"
            )
            return False
        
        # Request allowed - record timestamp
        requests.append(now)
        return True
    
    def get_remaining(self, user_id: int) -> dict:
        """Get remaining quota for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dict with remaining requests per time window
        """
        now = time.time()
        requests = self.user_requests.get(user_id, [])
        
        # Count requests in each window
        cutoff_minute = now - 60
        cutoff_hour = now - 3600
        cutoff_burst = now - 5
        
        minute_count = sum(1 for ts in requests if ts > cutoff_minute)
        hour_count = sum(1 for ts in requests if ts > cutoff_hour)
        burst_count = sum(1 for ts in requests if ts > cutoff_burst)
        
        return {
            'burst_remaining': max(0, self.config.burst_size - burst_count),
            'minute_remaining': max(0, self.config.requests_per_minute - minute_count),
            'hour_remaining': max(0, self.config.requests_per_hour - hour_count),
        }
    
    def reset_user(self, user_id: int):
        """Reset rate limits for a specific user (admin use).
        
        Args:
            user_id: Telegram user ID to reset
        """
        if user_id in self.user_requests:
            del self.user_requests[user_id]
            logger.info(f"Reset rate limits for user {user_id}")
    
    def _cleanup_old_requests(self):
        """Remove request data older than 1 hour to save memory."""
        now = time.time()
        cutoff = now - 3600
        
        # Clean up each user's request history
        for user_id in list(self.user_requests.keys()):
            requests = self.user_requests[user_id]
            cleaned = [ts for ts in requests if ts > cutoff]
            
            if cleaned:
                self.user_requests[user_id] = cleaned
            else:
                # No recent requests - remove entirely
                del self.user_requests[user_id]
        
        self.last_cleanup = now
        logger.debug(
            f"Cleaned up rate limiter. "
            f"Active users: {len(self.user_requests)}"
        )
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics.
        
        Returns:
            Dict with stats about active users and request counts
        """
        now = time.time()
        cutoff_hour = now - 3600
        
        total_users = len(self.user_requests)
        total_requests = sum(
            len([ts for ts in reqs if ts > cutoff_hour])
            for reqs in self.user_requests.values()
        )
        
        return {
            'active_users': total_users,
            'total_requests_last_hour': total_requests,
            'config': {
                'requests_per_minute': self.config.requests_per_minute,
                'requests_per_hour': self.config.requests_per_hour,
                'burst_size': self.config.burst_size,
            }
        }


# Global singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    requests_per_minute: int = 30,
    requests_per_hour: int = 500,
    burst_size: int = 5
) -> RateLimiter:
    """Get the global RateLimiter singleton.
    
    Args:
        requests_per_minute: Max requests per minute (default: 30)
        requests_per_hour: Max requests per hour (default: 500)
        burst_size: Max burst requests (default: 5)
        
    Returns:
        Initialized RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size
        )
    return _rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None
