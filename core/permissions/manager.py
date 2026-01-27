"""
Permission Manager for Jarvis.

Handles user permissions, exec request approval flow, and allowlist management.
Implements Clawdbot-style execution approval system.
"""

import fnmatch
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for users."""

    NONE = 0  # Read-only, cannot execute anything
    BASIC = 1  # Safe operations only
    ELEVATED = 2  # Most operations allowed
    ADMIN = 3  # Everything allowed, no approval needed

    @classmethod
    def from_string(cls, value: str) -> "PermissionLevel":
        """Convert string to PermissionLevel."""
        mapping = {
            "none": cls.NONE,
            "basic": cls.BASIC,
            "elevated": cls.ELEVATED,
            "admin": cls.ADMIN,
        }
        return mapping.get(value.lower(), cls.NONE)


# Action to minimum required permission level mapping
ACTION_PERMISSIONS = {
    # Safe actions (BASIC)
    "read_file": PermissionLevel.BASIC,
    "list_files": PermissionLevel.BASIC,
    "git_status": PermissionLevel.BASIC,
    "git_log": PermissionLevel.BASIC,
    "git_diff": PermissionLevel.BASIC,
    "view_config": PermissionLevel.BASIC,
    # Moderate actions (ELEVATED)
    "write_file": PermissionLevel.ELEVATED,
    "create_file": PermissionLevel.ELEVATED,
    "git_commit": PermissionLevel.ELEVATED,
    "run_script": PermissionLevel.ELEVATED,
    "install_package": PermissionLevel.ELEVATED,
    # Admin actions (ADMIN)
    "delete_system": PermissionLevel.ADMIN,
    "modify_permissions": PermissionLevel.ADMIN,
    "access_secrets": PermissionLevel.ADMIN,
    "force_push": PermissionLevel.ADMIN,
}


@dataclass
class ExecRequest:
    """Execution request requiring approval."""

    id: str
    user_id: int
    session_id: str
    command: str
    description: str = ""
    risk_level: str = "moderate"
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    approved_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if request has expired."""
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "command": self.command,
            "description": self.description,
            "risk_level": self.risk_level,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ExecRequest":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        elif expires_at is None:
            expires_at = datetime.now() + timedelta(minutes=5)

        approved_at = data.get("approved_at")
        if isinstance(approved_at, str):
            approved_at = datetime.fromisoformat(approved_at)

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            session_id=data["session_id"],
            command=data["command"],
            description=data.get("description", ""),
            risk_level=data.get("risk_level", "moderate"),
            status=data.get("status", "pending"),
            created_at=created_at,
            expires_at=expires_at,
            approved_at=approved_at,
        )


class PermissionManager:
    """
    Manages user permissions, exec requests, and allowlists.

    Thread-safe singleton implementation with SQLite persistence.
    """

    _instance: Optional["PermissionManager"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        """Ensure singleton instance."""
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """Initialize PermissionManager."""
        if self._initialized:
            return

        self.db_path = Path(db_path) if db_path else self._default_db_path()
        self._local = threading.local()

        # In-memory caches for performance
        self._user_levels: Dict[int, PermissionLevel] = {}
        self._requests: Dict[str, ExecRequest] = {}
        self._allowlists: Dict[int, List[str]] = {}

        # Initialize database
        self._init_db()
        self._initialized = True

        logger.info(f"PermissionManager initialized with db: {self.db_path}")

    def _default_db_path(self) -> Path:
        """Get default database path."""
        lifeos_dir = Path.home() / ".lifeos" / "permissions"
        lifeos_dir.mkdir(parents=True, exist_ok=True)
        return lifeos_dir / "permissions.db"

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                permission_level TEXT DEFAULT 'basic',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS exec_requests (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT,
                risk_level TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                approved_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS allowlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pattern TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pattern)
            );

            CREATE INDEX IF NOT EXISTS idx_exec_requests_user ON exec_requests(user_id);
            CREATE INDEX IF NOT EXISTS idx_exec_requests_status ON exec_requests(status);
            CREATE INDEX IF NOT EXISTS idx_allowlist_user ON allowlist(user_id);
            """
        )
        conn.commit()

    # User Permission Methods

    def get_user_level(self, user_id: int) -> PermissionLevel:
        """Get user's permission level."""
        # Check cache first
        if user_id in self._user_levels:
            return self._user_levels[user_id]

        # Query database
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT permission_level FROM users WHERE telegram_id = ?", (user_id,)
        )
        row = cursor.fetchone()

        if row:
            level = PermissionLevel.from_string(row["permission_level"])
        else:
            level = PermissionLevel.BASIC  # Default

        self._user_levels[user_id] = level
        return level

    def set_user_level(
        self, user_id: int, level: Union[PermissionLevel, str]
    ) -> None:
        """Set user's permission level."""
        if isinstance(level, str):
            level = PermissionLevel.from_string(level)

        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO users (telegram_id, permission_level)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET permission_level = ?
            """,
            (user_id, level.name.lower(), level.name.lower()),
        )
        conn.commit()

        # Update cache
        self._user_levels[user_id] = level
        logger.info(f"Set user {user_id} permission level to {level.name}")

    def check_permission(self, user_id: int, action: str) -> bool:
        """Check if user has permission for action."""
        user_level = self.get_user_level(user_id)

        # NONE level cannot do anything
        if user_level == PermissionLevel.NONE:
            return False

        # ADMIN can do everything
        if user_level == PermissionLevel.ADMIN:
            return True

        # Check action permission requirement
        required_level = ACTION_PERMISSIONS.get(action, PermissionLevel.ELEVATED)
        return user_level.value >= required_level.value

    # Exec Request Methods

    def request_approval(
        self,
        user_id: int,
        command: str,
        risk_level: str = "moderate",
        description: str = "",
        session_id: str = "",
    ) -> ExecRequest:
        """Create an exec request requiring approval."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"

        request = ExecRequest(
            id=request_id,
            user_id=user_id,
            session_id=session_id,
            command=command,
            description=description,
            risk_level=risk_level,
        )

        # Store in database
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO exec_requests
            (id, user_id, session_id, command, description, risk_level, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id,
                request.user_id,
                request.session_id,
                request.command,
                request.description,
                request.risk_level,
                request.status,
                request.created_at.isoformat(),
                request.expires_at.isoformat(),
            ),
        )
        conn.commit()

        # Cache
        self._requests[request_id] = request
        logger.info(f"Created exec request {request_id} for user {user_id}")

        return request

    def get_request(self, request_id: str) -> Optional[ExecRequest]:
        """Get exec request by ID."""
        # Check cache
        if request_id in self._requests:
            return self._requests[request_id]

        # Query database
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM exec_requests WHERE id = ?", (request_id,)
        )
        row = cursor.fetchone()

        if row:
            request = ExecRequest.from_dict(dict(row))
            self._requests[request_id] = request
            return request

        return None

    def approve_request(self, request_id: str) -> bool:
        """Approve an exec request."""
        request = self.get_request(request_id)
        if not request:
            return False

        if request.status != "pending":
            return False

        request.status = "approved"
        request.approved_at = datetime.now()

        # Update database
        conn = self._get_connection()
        conn.execute(
            "UPDATE exec_requests SET status = ?, approved_at = ? WHERE id = ?",
            (request.status, request.approved_at.isoformat(), request_id),
        )
        conn.commit()

        logger.info(f"Approved exec request {request_id}")
        return True

    def deny_request(self, request_id: str) -> bool:
        """Deny an exec request."""
        request = self.get_request(request_id)
        if not request:
            return False

        if request.status != "pending":
            return False

        request.status = "denied"

        # Update database
        conn = self._get_connection()
        conn.execute(
            "UPDATE exec_requests SET status = ? WHERE id = ?",
            (request.status, request_id),
        )
        conn.commit()

        logger.info(f"Denied exec request {request_id}")
        return True

    def list_pending_requests(
        self, user_id: Optional[int] = None
    ) -> List[ExecRequest]:
        """List pending exec requests, optionally filtered by user."""
        conn = self._get_connection()

        if user_id is not None:
            cursor = conn.execute(
                "SELECT * FROM exec_requests WHERE user_id = ? AND status = 'pending'",
                (user_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM exec_requests WHERE status = 'pending'"
            )

        requests = []
        for row in cursor.fetchall():
            request = ExecRequest.from_dict(dict(row))
            # Filter out expired requests
            if not request.is_expired():
                requests.append(request)
                self._requests[request.id] = request

        return requests

    # Allowlist Methods

    def add_to_allowlist(self, user_id: int, pattern: str) -> bool:
        """Add pattern to user's allowlist."""
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO allowlist (user_id, pattern) VALUES (?, ?)",
                (user_id, pattern),
            )
            conn.commit()

            # Update cache
            if user_id not in self._allowlists:
                self._allowlists[user_id] = []
            self._allowlists[user_id].append(pattern)

            logger.info(f"Added '{pattern}' to allowlist for user {user_id}")
            return True
        except sqlite3.IntegrityError:
            # Pattern already exists
            return False

    def remove_from_allowlist(self, user_id: int, pattern: str) -> bool:
        """Remove pattern from user's allowlist."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM allowlist WHERE user_id = ? AND pattern = ?",
            (user_id, pattern),
        )
        conn.commit()

        if cursor.rowcount > 0:
            # Update cache
            if user_id in self._allowlists and pattern in self._allowlists[user_id]:
                self._allowlists[user_id].remove(pattern)
            logger.info(f"Removed '{pattern}' from allowlist for user {user_id}")
            return True

        return False

    def get_allowlist(self, user_id: int) -> List[str]:
        """Get user's allowlist."""
        # Check cache
        if user_id in self._allowlists:
            return self._allowlists[user_id]

        # Query database
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT pattern FROM allowlist WHERE user_id = ?", (user_id,)
        )

        patterns = [row["pattern"] for row in cursor.fetchall()]
        self._allowlists[user_id] = patterns
        return patterns

    def is_allowlisted(self, user_id: int, command: str) -> bool:
        """Check if command matches user's allowlist."""
        allowlist = self.get_allowlist(user_id)

        for pattern in allowlist:
            if fnmatch.fnmatch(command, pattern):
                return True

        return False

    def close(self) -> None:
        """
        Close the database connection for the current thread.

        Note: This only closes the connection for the calling thread.
        Other threads' connections remain open. For full cleanup,
        call close() from each thread that used the manager.
        """
        if hasattr(self._local, "connection") and self._local.connection is not None:
            try:
                self._local.connection.close()
                self._local.connection = None
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")


# Module-level singleton management

_manager: Optional[PermissionManager] = None
_manager_lock = threading.Lock()


def get_permission_manager(db_path: Optional[str] = None) -> PermissionManager:
    """Get or create global PermissionManager instance."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = PermissionManager(db_path)
    return _manager


def _reset_manager() -> None:
    """Reset singleton for testing."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            # Close connections
            if hasattr(_manager, "_local") and hasattr(_manager._local, "connection"):
                try:
                    _manager._local.connection.close()
                except Exception:
                    pass
            _manager = None
        # Reset class-level singleton
        PermissionManager._instance = None
