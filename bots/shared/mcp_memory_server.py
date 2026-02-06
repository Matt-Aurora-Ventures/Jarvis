#!/usr/bin/env python3
"""
MCP Memory Server for ClawdBot
Provides SuperMemory functionality via MCP protocol.
Replaces OpenAI embeddings with local SQLite-based memory.

Usage:
    python mcp_memory_server.py --bot friday

Clawdbot config:
    "mcp": {
        "servers": {
            "memory": {
                "command": "python",
                "args": ["/root/clawd/mcp_memory_server.py", "--bot", "friday"]
            }
        }
    }
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from bots.shared.supermemory import SuperMemory
except ImportError:
    # Fallback for standalone deployment
    import sqlite3
    from datetime import datetime, timezone

    class SuperMemory:
        """Minimal standalone SuperMemory for MCP server."""

        TAG_PERMISSIONS = {
            "company_core": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
            "technical_stack": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
            "marketing_creative": {"read": ["matt", "friday"], "write": ["friday"]},
            "crypto_ops": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
            "ops_logs": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
            "shared": {"read": ["matt", "friday", "jarvis"], "write": ["matt", "friday", "jarvis"]},
        }

        def __init__(self, bot_name: str, db_path: str = "/root/clawdbots/data/supermemory.db"):
            self.bot_name = bot_name.lower()
            self.db_path = db_path
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

        def _get_conn(self):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

        def _init_db(self):
            conn = self._get_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    author TEXT NOT NULL,
                    document_date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_facts_tag ON facts(tag);
            """)
            conn.commit()
            conn.close()

        def can_read(self, tag: str) -> bool:
            perms = self.TAG_PERMISSIONS.get(tag, self.TAG_PERMISSIONS.get("shared"))
            return self.bot_name in perms.get("read", [])

        def can_write(self, tag: str) -> bool:
            perms = self.TAG_PERMISSIONS.get(tag, self.TAG_PERMISSIONS.get("shared"))
            return self.bot_name in perms.get("write", [])

        def remember(self, content: str, tag: str = "shared") -> int:
            if not self.can_write(tag):
                tag = "shared"  # Fallback to shared
            now = datetime.now(timezone.utc).isoformat()
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO facts (content, tag, author, document_date, created_at) VALUES (?, ?, ?, ?, ?)",
                (content, tag, self.bot_name, now, now)
            )
            conn.commit()
            fid = cursor.lastrowid
            conn.close()
            return fid

        def recall(self, query: str, tag: str = None, limit: int = 10) -> list:
            conn = self._get_conn()
            conditions = []
            params = []

            if query:
                conditions.append("content LIKE ?")
                params.append(f"%{query}%")

            if tag and self.can_read(tag):
                conditions.append("tag = ?")
                params.append(tag)
            else:
                readable = [t for t in self.TAG_PERMISSIONS if self.can_read(t)]
                if readable:
                    placeholders = ",".join("?" * len(readable))
                    conditions.append(f"tag IN ({placeholders})")
                    params.extend(readable)

            where = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)

            rows = conn.execute(
                f"SELECT id, content, tag, author, document_date FROM facts WHERE {where} ORDER BY document_date DESC LIMIT ?",
                params
            ).fetchall()
            conn.close()

            return [{"id": r["id"], "content": r["content"], "tag": r["tag"], "author": r["author"]} for r in rows]


class MCPMemoryServer:
    """MCP server providing memory tools."""

    def __init__(self, bot_name: str):
        self.memory = SuperMemory(bot_name)
        self.bot_name = bot_name

    def handle_request(self, request: dict) -> dict:
        """Handle MCP JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                return self._response(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "supermemory", "version": "1.0.0"}
                })

            elif method == "tools/list":
                return self._response(req_id, {
                    "tools": [
                        {
                            "name": "memory_remember",
                            "description": "Store a fact in shared team memory",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "content": {"type": "string", "description": "The fact to remember"},
                                    "tag": {"type": "string", "description": "Category tag", "default": "shared"}
                                },
                                "required": ["content"]
                            }
                        },
                        {
                            "name": "memory_recall",
                            "description": "Search team memory for relevant facts",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"},
                                    "limit": {"type": "integer", "description": "Max results", "default": 10}
                                },
                                "required": ["query"]
                            }
                        }
                    ]
                })

            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})

                if tool_name == "memory_remember":
                    fid = self.memory.remember(args["content"], args.get("tag", "shared"))
                    return self._response(req_id, {
                        "content": [{"type": "text", "text": f"Stored fact #{fid}"}]
                    })

                elif tool_name == "memory_recall":
                    results = self.memory.recall(args["query"], limit=args.get("limit", 10))
                    if results:
                        text = "\n".join([f"[{r['tag']}] {r['content']} (by {r['author']})" for r in results])
                    else:
                        text = "No matching memories found."
                    return self._response(req_id, {
                        "content": [{"type": "text", "text": text}]
                    })

                else:
                    return self._error(req_id, -32601, f"Unknown tool: {tool_name}")

            elif method == "notifications/initialized":
                return None  # No response needed

            else:
                return self._error(req_id, -32601, f"Method not found: {method}")

        except Exception as e:
            return self._error(req_id, -32603, str(e))

    def _response(self, req_id, result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id, code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    def run(self):
        """Run the MCP server on stdin/stdout."""
        sys.stderr.write(f"[supermemory] MCP server started for bot: {self.bot_name}\n")
        sys.stderr.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError as e:
                sys.stderr.write(f"[supermemory] JSON error: {e}\n")
                sys.stderr.flush()


def main():
    parser = argparse.ArgumentParser(description="MCP Memory Server")
    parser.add_argument("--bot", required=True, help="Bot name (friday/matt/jarvis)")
    args = parser.parse_args()

    server = MCPMemoryServer(args.bot)
    server.run()


if __name__ == "__main__":
    main()
