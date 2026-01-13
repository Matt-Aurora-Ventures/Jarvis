"""Secure session management."""
import secrets
import time
import hashlib
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


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


session_manager = SecureSessionManager()
