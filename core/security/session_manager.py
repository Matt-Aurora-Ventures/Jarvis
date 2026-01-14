"""
JARVIS Secure Session Management

Provides session management with timeout enforcement,
secure token generation, and session lifecycle management.
"""
import secrets
import time
import hashlib
import asyncio
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class Session:
    user_id: str
    ip_address: str
    user_agent: str = ""
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True


class SecureSessionManager:
    """Manage secure user sessions."""
    
    def __init__(
        self, 
        session_timeout: int = 3600,
        max_sessions_per_user: int = 5,
        bind_to_ip: bool = True
    ):
        self.session_timeout = session_timeout
        self.max_sessions_per_user = max_sessions_per_user
        self.bind_to_ip = bind_to_ip
        self.sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, list] = {}
    
    def create_session(
        self, 
        user_id: str, 
        ip_address: str,
        user_agent: str = "",
        data: Dict[str, Any] = None
    ) -> str:
        """Create a new session."""
        self._enforce_session_limit(user_id)
        
        session_id = self._generate_session_id()
        
        session = Session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            data=data or {}
        )
        
        self.sessions[session_id] = session
        
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)
        
        logger.info(f"Created session for user {user_id} from {ip_address}")
        return session_id
    
    def get_session(self, session_id: str, ip_address: str = None) -> Optional[Session]:
        """Get a session by ID."""
        session = self.sessions.get(session_id)
        
        if not session:
            return None
        
        if not session.is_valid:
            return None
        
        if self._is_expired(session):
            self.invalidate_session(session_id)
            return None
        
        if self.bind_to_ip and ip_address and session.ip_address != ip_address:
            logger.warning(f"Session {session_id[:8]}... IP mismatch: {session.ip_address} vs {ip_address}")
            return None
        
        session.last_activity = time.time()
        return session
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.is_valid = False
        
        if session.user_id in self._user_sessions:
            if session_id in self._user_sessions[session.user_id]:
                self._user_sessions[session.user_id].remove(session_id)
        
        del self.sessions[session_id]
        logger.info(f"Invalidated session {session_id[:8]}...")
        return True
    
    def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        session_ids = self._user_sessions.get(user_id, []).copy()
        count = 0
        
        for session_id in session_ids:
            if self.invalidate_session(session_id):
                count += 1
        
        return count
    
    def update_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        session = self.sessions.get(session_id)
        if not session or not session.is_valid:
            return False
        
        session.data.update(data)
        session.last_activity = time.time()
        return True
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        expired = []
        for session_id, session in self.sessions.items():
            if self._is_expired(session):
                expired.append(session_id)
        
        for session_id in expired:
            self.invalidate_session(session_id)
        
        return len(expired)
    
    def get_user_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user."""
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []
        
        for session_id in session_ids:
            session = self.sessions.get(session_id)
            if session and session.is_valid and not self._is_expired(session):
                sessions.append({
                    "session_id": session_id[:8] + "...",
                    "ip_address": session.ip_address,
                    "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
                    "last_activity": datetime.fromtimestamp(session.last_activity).isoformat()
                })
        
        return sessions
    
    def _generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)
    
    def _is_expired(self, session: Session) -> bool:
        """Check if a session is expired."""
        return time.time() - session.last_activity > self.session_timeout
    
    def _enforce_session_limit(self, user_id: str):
        """Enforce max sessions per user."""
        session_ids = self._user_sessions.get(user_id, [])
        
        if len(session_ids) >= self.max_sessions_per_user:
            oldest = min(
                session_ids,
                key=lambda sid: self.sessions.get(sid, Session("", "")).created_at
            )
            self.invalidate_session(oldest)
            logger.info(f"Removed oldest session for user {user_id} due to limit")


class SessionTimeoutEnforcer:
    """
    Enforces session timeouts with background cleanup.

    Features:
    - Configurable absolute and idle timeouts
    - Background cleanup task
    - Session state tracking
    - Async support

    Usage:
        enforcer = SessionTimeoutEnforcer(session_manager)
        await enforcer.start()

        # Check timeout
        if enforcer.is_session_timed_out(session_id):
            # Handle timeout
    """

    def __init__(
        self,
        manager: SecureSessionManager,
        absolute_timeout: int = 86400,  # 24 hours
        idle_timeout: int = 3600,  # 1 hour
        cleanup_interval: int = 60  # 1 minute
    ):
        self.manager = manager
        self.absolute_timeout = absolute_timeout
        self.idle_timeout = idle_timeout
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._session_states: Dict[str, SessionState] = {}

    async def start(self) -> None:
        """Start the timeout enforcement background task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session timeout enforcer started")

    async def stop(self) -> None:
        """Stop the timeout enforcement."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Session timeout enforcer stopped")

    def check_session(self, session_id: str) -> SessionState:
        """Check the current state of a session."""
        session = self.manager.sessions.get(session_id)

        if not session:
            return SessionState.EXPIRED

        if not session.is_valid:
            return SessionState.REVOKED

        now = time.time()

        # Check absolute timeout
        if now - session.created_at > self.absolute_timeout:
            self._session_states[session_id] = SessionState.EXPIRED
            return SessionState.EXPIRED

        # Check idle timeout
        if now - session.last_activity > self.idle_timeout:
            self._session_states[session_id] = SessionState.IDLE
            return SessionState.IDLE

        self._session_states[session_id] = SessionState.ACTIVE
        return SessionState.ACTIVE

    def is_session_timed_out(self, session_id: str) -> bool:
        """Check if a session has timed out."""
        state = self.check_session(session_id)
        return state in (SessionState.EXPIRED, SessionState.IDLE, SessionState.REVOKED)

    def get_remaining_time(self, session_id: str) -> Dict[str, int]:
        """Get remaining time before timeouts."""
        session = self.manager.sessions.get(session_id)

        if not session:
            return {"absolute": 0, "idle": 0}

        now = time.time()

        absolute_remaining = max(0, int(
            self.absolute_timeout - (now - session.created_at)
        ))
        idle_remaining = max(0, int(
            self.idle_timeout - (now - session.last_activity)
        ))

        return {
            "absolute": absolute_remaining,
            "idle": idle_remaining,
            "effective": min(absolute_remaining, idle_remaining)
        }

    async def _cleanup_loop(self) -> None:
        """Background task to enforce timeouts."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._enforce_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session timeout enforcement: {e}")

    async def _enforce_timeouts(self) -> int:
        """Enforce timeouts on all sessions."""
        expired_count = 0
        now = time.time()

        for session_id in list(self.manager.sessions.keys()):
            session = self.manager.sessions.get(session_id)
            if not session:
                continue

            # Check absolute timeout
            if now - session.created_at > self.absolute_timeout:
                self.manager.invalidate_session(session_id)
                self._session_states[session_id] = SessionState.EXPIRED
                expired_count += 1
                logger.info(f"Session {session_id[:8]}... expired (absolute timeout)")
                continue

            # Check idle timeout
            if now - session.last_activity > self.idle_timeout:
                self.manager.invalidate_session(session_id)
                self._session_states[session_id] = SessionState.IDLE
                expired_count += 1
                logger.info(f"Session {session_id[:8]}... expired (idle timeout)")

        if expired_count > 0:
            logger.info(f"Enforced timeout on {expired_count} sessions")

        return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """Get timeout enforcement statistics."""
        states = {}
        for state in SessionState:
            states[state.value] = sum(
                1 for s in self._session_states.values() if s == state
            )

        return {
            "absolute_timeout": self.absolute_timeout,
            "idle_timeout": self.idle_timeout,
            "session_states": states,
            "total_tracked": len(self._session_states)
        }


# Global instances
session_manager = SecureSessionManager()
timeout_enforcer: Optional[SessionTimeoutEnforcer] = None


def get_session_manager() -> SecureSessionManager:
    """Get the global session manager."""
    return session_manager


def get_timeout_enforcer() -> SessionTimeoutEnforcer:
    """Get or create the global timeout enforcer."""
    global timeout_enforcer
    if timeout_enforcer is None:
        timeout_enforcer = SessionTimeoutEnforcer(session_manager)
    return timeout_enforcer


async def start_session_management() -> None:
    """Start session management with timeout enforcement."""
    enforcer = get_timeout_enforcer()
    await enforcer.start()


async def stop_session_management() -> None:
    """Stop session management."""
    global timeout_enforcer
    if timeout_enforcer:
        await timeout_enforcer.stop()
