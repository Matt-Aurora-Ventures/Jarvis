"""MCP server that launches and validates the Jarvis trading web UI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

DEFAULT_ROOT = r"C:\Users\lucid\Desktop\Jarvis"
ROOT = os.environ.get("JARVIS_ROOT", DEFAULT_ROOT)
PYTHON = os.environ.get("JARVIS_TRADING_PYTHON", "python")
LOG_PATH = os.path.join(ROOT, "logs", "trading_web.log")

os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)

_proc: subprocess.Popen[str] | None = None
_log_handle = None


def _read_log_tail(max_lines: int = 25) -> str:
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return "(log file not found)"
    except Exception as exc:  # pragma: no cover - defensive path
        return f"(unable to read log: {exc})"

    return "".join(lines[-max_lines:]).strip() or "(log file is empty)"


def _send(obj: dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    os.write(sys.stdout.fileno(), line.encode("utf-8"))


def _send_error(mid: Any, code: int, message: str, data: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    _send(payload)


def _is_alive() -> bool:
    return _proc is not None and _proc.poll() is None


def ensure_flask() -> tuple[bool, dict[str, Any] | None]:
    """Start Flask when needed and verify it did not crash immediately."""
    global _proc, _log_handle
    if _is_alive():
        return True, None

    if _log_handle is not None:
        try:
            _log_handle.close()
        except Exception:
            pass
        _log_handle = None

    _log_handle = open(LOG_PATH, "w", encoding="utf-8", errors="replace")
    try:
        _proc = subprocess.Popen(
            [PYTHON, os.path.join(ROOT, "web", "trading_web.py")],
            stdout=_log_handle,
            stderr=_log_handle,
            cwd=ROOT,
        )
    except OSError as exc:
        return False, {
            "status": "failed",
            "exitCode": None,
            "logPath": LOG_PATH,
            "error": str(exc),
            "logTail": _read_log_tail(),
        }

    # Allow immediate import/runtime failures to surface before reporting "running".
    time.sleep(0.6)
    if _proc.poll() is not None:
        return False, {
            "status": "failed",
            "exitCode": _proc.returncode,
            "logPath": LOG_PATH,
            "logTail": _read_log_tail(),
        }

    return True, {"status": "running", "url": "http://127.0.0.1:5001", "pid": _proc.pid}


def _status_payload() -> dict[str, Any]:
    if _is_alive():
        assert _proc is not None
        return {
            "status": "running",
            "url": "http://127.0.0.1:5001",
            "pid": _proc.pid,
            "logPath": LOG_PATH,
        }

    if _proc is None:
        return {
            "status": "stopped",
            "logPath": LOG_PATH,
            "logTail": _read_log_tail(),
        }

    return {
        "status": "failed",
        "exitCode": _proc.returncode,
        "logPath": LOG_PATH,
        "logTail": _read_log_tail(),
    }


for raw in sys.stdin.buffer:
    try:
        msg = json.loads(raw)
        method, mid = msg.get("method", ""), msg.get("id")

        if method == "initialize":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "trading-launcher", "version": "1.1.0"},
                    },
                }
            )
            continue

        if method == "tools/list":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "tools": [
                            {
                                "name": "trading_status",
                                "description": "Get Jarvis Trading UI status and URL if healthy.",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                        ]
                    },
                }
            )
            continue

        if method == "tools/call":
            ok, details = ensure_flask()
            if not ok:
                _send_error(
                    mid,
                    -32000,
                    "Trading UI failed to start",
                    details,
                )
                continue

            _send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Trading UI is running at http://127.0.0.1:5001",
                            },
                            {"type": "text", "text": json.dumps(details, ensure_ascii=False)},
                        ]
                    },
                }
            )
            continue

        if method == "trading/status":
            _send({"jsonrpc": "2.0", "id": mid, "result": _status_payload()})
            continue

        if mid is not None:
            _send_error(mid, -32601, "Method not found")
    except Exception:
        # Keep server loop alive for malformed client payloads.
        continue
