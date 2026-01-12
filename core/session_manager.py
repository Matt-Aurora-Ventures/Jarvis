"""
Session Manager - Manage trading sessions, state, and context.
Handles session lifecycle, state persistence, and recovery.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import json
import uuid


class SessionState(Enum):
    """Session states."""
    CREATED = "created"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERED = "recovered"


class SessionType(Enum):
    """Types of sessions."""
    TRADING = "trading"
    MONITORING = "monitoring"
    BACKTESTING = "backtesting"
    PAPER_TRADING = "paper_trading"
    ANALYSIS = "analysis"


@dataclass
class SessionConfig:
    """Session configuration."""
    session_type: SessionType
    auto_recovery: bool = True
    checkpoint_interval_seconds: int = 60
    max_idle_seconds: int = 3600
    persist_state: bool = True
    state_encryption: bool = False


@dataclass
class Session:
    """A trading session."""
    session_id: str
    session_type: SessionType
    state: SessionState
    config: SessionConfig
    created_at: datetime
    started_at: Optional[datetime]
    last_activity: datetime
    checkpoint_data: Dict
    error_message: Optional[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class SessionCheckpoint:
    """Session checkpoint for recovery."""
    checkpoint_id: str
    session_id: str
    timestamp: datetime
    state: SessionState
    data: Dict
    version: int


@dataclass
class SessionEvent:
    """Session event."""
    event_id: str
    session_id: str
    event_type: str
    timestamp: datetime
    details: Dict


class SessionManager:
    """
    Manages trading sessions with state persistence and recovery.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "sessions.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.sessions: Dict[str, Session] = {}
        self.current_session: Optional[Session] = None

        # Event handlers
        self.state_change_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []

        # Checkpoint task
        self._checkpoint_task: Optional[asyncio.Task] = None
        self._running = False

        self._lock = threading.Lock()

        # Load active sessions
        self._load_active_sessions()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    session_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    config TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    last_activity TEXT NOT NULL,
                    checkpoint_data TEXT,
                    error_message TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS session_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);
                CREATE INDEX IF NOT EXISTS idx_events_session ON session_events(session_id);
            """)

    def _load_active_sessions(self):
        """Load active sessions from database."""
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM sessions
                WHERE state NOT IN ('stopped', 'error')
            """).fetchall()

            for row in rows:
                session = self._row_to_session(row)
                self.sessions[session.session_id] = session

    def _row_to_session(self, row) -> Session:
        """Convert database row to Session."""
        config_data = json.loads(row["config"])
        return Session(
            session_id=row["session_id"],
            session_type=SessionType(row["session_type"]),
            state=SessionState(row["state"]),
            config=SessionConfig(
                session_type=SessionType(config_data["session_type"]),
                auto_recovery=config_data.get("auto_recovery", True),
                checkpoint_interval_seconds=config_data.get("checkpoint_interval_seconds", 60),
                max_idle_seconds=config_data.get("max_idle_seconds", 3600),
                persist_state=config_data.get("persist_state", True),
                state_encryption=config_data.get("state_encryption", False)
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            last_activity=datetime.fromisoformat(row["last_activity"]),
            checkpoint_data=json.loads(row["checkpoint_data"] or "{}"),
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"] or "{}")
        )

    def create_session(
        self,
        session_type: SessionType = SessionType.TRADING,
        config: Optional[SessionConfig] = None,
        metadata: Optional[Dict] = None
    ) -> Session:
        """Create a new session."""
        if config is None:
            config = SessionConfig(session_type=session_type)

        now = datetime.now()
        session = Session(
            session_id=str(uuid.uuid4())[:12],
            session_type=session_type,
            state=SessionState.CREATED,
            config=config,
            created_at=now,
            started_at=None,
            last_activity=now,
            checkpoint_data={},
            error_message=None,
            metadata=metadata or {}
        )

        with self._lock:
            self.sessions[session.session_id] = session

        self._save_session(session)
        self._record_event(session.session_id, "created", {"type": session_type.value})

        return session

    def _save_session(self, session: Session):
        """Save session to database."""
        config_dict = {
            "session_type": session.config.session_type.value,
            "auto_recovery": session.config.auto_recovery,
            "checkpoint_interval_seconds": session.config.checkpoint_interval_seconds,
            "max_idle_seconds": session.config.max_idle_seconds,
            "persist_state": session.config.persist_state,
            "state_encryption": session.config.state_encryption
        }

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, session_type, state, config, created_at,
                 started_at, last_activity, checkpoint_data, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id, session.session_type.value,
                session.state.value, json.dumps(config_dict),
                session.created_at.isoformat(),
                session.started_at.isoformat() if session.started_at else None,
                session.last_activity.isoformat(),
                json.dumps(session.checkpoint_data),
                session.error_message,
                json.dumps(session.metadata)
            ))

    def _record_event(self, session_id: str, event_type: str, details: Dict):
        """Record a session event."""
        event_id = str(uuid.uuid4())[:12]
        now = datetime.now()

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO session_events
                (event_id, session_id, event_type, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, session_id, event_type, now.isoformat(), json.dumps(details)))

    async def start_session(self, session_id: str) -> Session:
        """Start a session."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        old_state = session.state
        session.state = SessionState.STARTING
        session.started_at = datetime.now()
        session.last_activity = datetime.now()

        self._save_session(session)
        self._notify_state_change(session, old_state)

        # Start checkpoint task if needed
        if session.config.persist_state:
            await self._start_checkpoint_task(session)

        session.state = SessionState.ACTIVE
        self._save_session(session)
        self._record_event(session_id, "started", {})

        self.current_session = session
        return session

    async def _start_checkpoint_task(self, session: Session):
        """Start periodic checkpoint task."""
        self._running = True

        async def checkpoint_loop():
            while self._running:
                await asyncio.sleep(session.config.checkpoint_interval_seconds)
                if session.state == SessionState.ACTIVE:
                    self.save_checkpoint(session.session_id)

        self._checkpoint_task = asyncio.create_task(checkpoint_loop())

    def pause_session(self, session_id: str) -> Session:
        """Pause a session."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        old_state = session.state
        session.state = SessionState.PAUSED
        session.last_activity = datetime.now()

        self._save_session(session)
        self._record_event(session_id, "paused", {})
        self._notify_state_change(session, old_state)

        return session

    def resume_session(self, session_id: str) -> Session:
        """Resume a paused session."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.state != SessionState.PAUSED:
            raise ValueError(f"Session is not paused: {session.state}")

        old_state = session.state
        session.state = SessionState.ACTIVE
        session.last_activity = datetime.now()

        self._save_session(session)
        self._record_event(session_id, "resumed", {})
        self._notify_state_change(session, old_state)

        return session

    def stop_session(self, session_id: str) -> Session:
        """Stop a session."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        old_state = session.state
        session.state = SessionState.STOPPING
        self._save_session(session)

        # Stop checkpoint task
        self._running = False
        if self._checkpoint_task:
            self._checkpoint_task.cancel()

        # Final checkpoint
        self.save_checkpoint(session_id)

        session.state = SessionState.STOPPED
        session.last_activity = datetime.now()

        self._save_session(session)
        self._record_event(session_id, "stopped", {})
        self._notify_state_change(session, old_state)

        if self.current_session and self.current_session.session_id == session_id:
            self.current_session = None

        return session

    def save_checkpoint(self, session_id: str, data: Optional[Dict] = None) -> SessionCheckpoint:
        """Save a session checkpoint."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get latest version
        with self._get_db() as conn:
            row = conn.execute("""
                SELECT MAX(version) as max_version FROM checkpoints
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            version = (row["max_version"] or 0) + 1

        now = datetime.now()
        checkpoint = SessionCheckpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            session_id=session_id,
            timestamp=now,
            state=session.state,
            data=data or session.checkpoint_data,
            version=version
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO checkpoints
                (checkpoint_id, session_id, timestamp, state, data, version)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                checkpoint.checkpoint_id, session_id,
                now.isoformat(), session.state.value,
                json.dumps(checkpoint.data), version
            ))

        return checkpoint

    def update_state(self, session_id: str, data: Dict):
        """Update session state data."""
        session = self.sessions.get(session_id)
        if not session:
            return

        session.checkpoint_data.update(data)
        session.last_activity = datetime.now()
        self._save_session(session)

    def get_state(self, session_id: str, key: Optional[str] = None) -> Any:
        """Get session state data."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        if key:
            return session.checkpoint_data.get(key)
        return session.checkpoint_data

    def recover_session(self, session_id: str) -> Session:
        """Recover a session from the latest checkpoint."""
        # Get latest checkpoint
        with self._get_db() as conn:
            row = conn.execute("""
                SELECT * FROM checkpoints
                WHERE session_id = ?
                ORDER BY version DESC LIMIT 1
            """, (session_id,)).fetchone()

        if not row:
            raise ValueError(f"No checkpoint found for session: {session_id}")

        session = self.sessions.get(session_id)
        if not session:
            # Reload from database
            with self._get_db() as conn:
                session_row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?",
                    (session_id,)
                ).fetchone()
                if session_row:
                    session = self._row_to_session(session_row)
                    self.sessions[session_id] = session

        if session:
            old_state = session.state
            session.checkpoint_data = json.loads(row["data"])
            session.state = SessionState.RECOVERED
            session.last_activity = datetime.now()

            self._save_session(session)
            self._record_event(session_id, "recovered", {"version": row["version"]})
            self._notify_state_change(session, old_state)

        return session

    def _notify_state_change(self, session: Session, old_state: SessionState):
        """Notify handlers of state change."""
        for handler in self.state_change_handlers:
            try:
                handler(session, old_state, session.state)
            except Exception:
                pass

    def register_state_handler(
        self,
        handler: Callable[[Session, SessionState, SessionState], None]
    ):
        """Register handler for state changes."""
        self.state_change_handlers.append(handler)

    def register_error_handler(
        self,
        handler: Callable[[Session, Exception], None]
    ):
        """Register handler for errors."""
        self.error_handlers.append(handler)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def get_active_sessions(self) -> List[Session]:
        """Get all active sessions."""
        return [
            s for s in self.sessions.values()
            if s.state in [SessionState.ACTIVE, SessionState.PAUSED]
        ]

    def get_session_events(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[SessionEvent]:
        """Get events for a session."""
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM session_events
                WHERE session_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (session_id, limit)).fetchall()

            return [
                SessionEvent(
                    event_id=row["event_id"],
                    session_id=row["session_id"],
                    event_type=row["event_type"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    details=json.loads(row["details"] or "{}")
                )
                for row in rows
            ]


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
