"""
Telegram-Console Bridge for Vibe Coding.

This module enables admin users to send coding requests from Telegram
that get relayed to the console for execution by Cascade/Claude.

Features:
- Persistent memory for conversation context
- Request queue for console pickup
- Context-aware responses
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import threading

# Paths
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REQUESTS_FILE = DATA_DIR / "console_requests.json"
MEMORY_DB = DATA_DIR / "telegram_memory.db"


@dataclass
class ConsoleRequest:
    """A request from Telegram to be executed in console."""
    id: str
    user_id: int
    username: str
    message: str
    context: str  # Recent conversation context
    created_at: str
    status: str  # pending, processing, completed, failed
    result: Optional[str] = None
    completed_at: Optional[str] = None


class TelegramMemory:
    """Persistent memory for Telegram conversations."""
    
    def __init__(self, db_path: Path = MEMORY_DB):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Conversation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    role TEXT,  -- 'user' or 'assistant'
                    content TEXT,
                    timestamp TEXT,
                    chat_id INTEGER
                )
            """)
            
            # Learned facts/preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    key TEXT,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(user_id, key)
                )
            """)
            
            # Pending instructions from admin
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instruction TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    active INTEGER DEFAULT 1
                )
            """)
            
            conn.commit()
            conn.close()
    
    def add_message(self, user_id: int, username: str, role: str, content: str, chat_id: int = 0):
        """Add a message to conversation history."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (user_id, username, role, content, timestamp, chat_id) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, role, content, datetime.now(timezone.utc).isoformat(), chat_id)
            )
            conn.commit()
            conn.close()
    
    def get_recent_context(self, user_id: int = None, limit: int = 20) -> List[Dict]:
        """Get recent conversation context."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute(
                    "SELECT username, role, content, timestamp FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT username, role, content, timestamp FROM messages ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            
            rows = cursor.fetchall()
            conn.close()
            
            # Reverse to get chronological order
            return [
                {"username": r[0], "role": r[1], "content": r[2], "timestamp": r[3]}
                for r in reversed(rows)
            ]
    
    def store_memory(self, user_id: int, key: str, value: str):
        """Store a learned fact or preference."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """INSERT INTO memories (user_id, key, value, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, key) DO UPDATE SET value=?, updated_at=?""",
                (user_id, key, value, now, now, value, now)
            )
            conn.commit()
            conn.close()
    
    def get_memories(self, user_id: int) -> Dict[str, str]:
        """Get all stored memories for a user."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM memories WHERE user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
    
    def add_instruction(self, instruction: str, created_by: int):
        """Add a standing instruction (e.g., 'reply with contract for KR8TIV')."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO instructions (instruction, created_by, created_at) VALUES (?, ?, ?)",
                (instruction, created_by, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
    
    def get_active_instructions(self) -> List[str]:
        """Get all active standing instructions."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT instruction FROM instructions WHERE active = 1"
            )
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]


class ConsoleBridge:
    """Bridge between Telegram and Console for vibe coding."""
    
    def __init__(self):
        self.memory = TelegramMemory()
        self._ensure_requests_file()
    
    def _ensure_requests_file(self):
        """Ensure the requests file exists."""
        if not REQUESTS_FILE.exists():
            REQUESTS_FILE.write_text("[]")
    
    def _load_requests(self) -> List[Dict]:
        """Load pending requests."""
        try:
            return json.loads(REQUESTS_FILE.read_text())
        except:
            return []
    
    def _save_requests(self, requests: List[Dict]):
        """Save requests to file."""
        REQUESTS_FILE.write_text(json.dumps(requests, indent=2))
    
    def queue_request(self, user_id: int, username: str, message: str) -> str:
        """Queue a coding request for console pickup."""
        # Get recent context
        context = self.memory.get_recent_context(user_id, limit=10)
        context_str = "\n".join([
            f"[{m['role']}] {m['content'][:200]}" for m in context
        ])
        
        # Create request
        request_id = f"req_{int(time.time())}_{user_id}"
        request = ConsoleRequest(
            id=request_id,
            user_id=user_id,
            username=username,
            message=message,
            context=context_str,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="pending"
        )
        
        # Save to file
        requests = self._load_requests()
        requests.append(asdict(request))
        self._save_requests(requests)
        
        # Also log the message
        self.memory.add_message(user_id, username, "user", message)
        
        return request_id
    
    def get_pending_requests(self) -> List[Dict]:
        """Get all pending requests for console."""
        requests = self._load_requests()
        return [r for r in requests if r.get("status") == "pending"]
    
    def mark_processing(self, request_id: str):
        """Mark a request as being processed."""
        requests = self._load_requests()
        for r in requests:
            if r["id"] == request_id:
                r["status"] = "processing"
                break
        self._save_requests(requests)
    
    def complete_request(self, request_id: str, result: str):
        """Mark a request as completed with result."""
        requests = self._load_requests()
        user_id = None
        for r in requests:
            if r["id"] == request_id:
                r["status"] = "completed"
                r["result"] = result
                r["completed_at"] = datetime.now(timezone.utc).isoformat()
                user_id = r.get("user_id")
                
                # Store the response in memory
                self.memory.add_message(r["user_id"], "jarvis", "assistant", result)
                break
        self._save_requests(requests)
        return user_id
    
    async def send_telegram_feedback(self, request_id: str, message: str, chat_id: str = None):
        """Send feedback to Telegram about a request."""
        import aiohttp
        import os
        
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not chat_id:
            chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
        
        if not bot_token or not chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }) as resp:
                data = await resp.json()
                return data.get("ok", False)
    
    def is_coding_request(self, message: str) -> bool:
        """Detect if a message is a coding/development request."""
        coding_keywords = [
            "fix", "add", "create", "build", "implement", "change",
            "update", "modify", "refactor", "debug", "test", "deploy",
            "code", "function", "class", "api", "endpoint", "command",
            "feature", "bug", "error", "issue", "make", "write",
            "ralph wiggum", "cascade", "vibe code", "console"
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in coding_keywords)


# Singleton
_bridge: Optional[ConsoleBridge] = None

def get_console_bridge() -> ConsoleBridge:
    """Get the singleton ConsoleBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = ConsoleBridge()
    return _bridge
