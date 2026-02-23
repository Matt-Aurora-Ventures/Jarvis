#!/usr/bin/env python3
"""Validate NotebookLM MCP configuration and notebook selection."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG = ROOT / ".mcp.json"
DEFAULT_NOTEBOOK_URL = "https://notebooklm.google.com/notebook/cfd9d32c-4d31-432c-a5dd-807805467705"
SELECTION_FILE = ROOT / ".runtime" / "notebooklm" / "notebook_selection.json"


VERSION_PATTERN = re.compile(r"^notebooklm-mcp@\d+\.\d+\.\d+$")
URL_PATTERN = re.compile(r"^https://notebooklm\.google\.com/notebook/[a-f0-9\-]+$")


def load_notebooklm_server() -> dict:
    if not MCP_CONFIG.exists():
        raise FileNotFoundError(f"Missing MCP config: {MCP_CONFIG}")
    cfg = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    server = cfg.get("mcpServers", {}).get("notebooklm")
    if not server:
        raise RuntimeError("NotebookLM MCP server entry is missing from .mcp.json")
    return server


def resolve_pinned_package(args_list: list[str]) -> str:
    for token in args_list:
        if token.startswith("notebooklm-mcp@"):
            if token.endswith("@latest") or token == "notebooklm-mcp":
                raise RuntimeError("NotebookLM MCP must be pinned to an explicit version")
            if not VERSION_PATTERN.match(token):
                raise RuntimeError(f"Invalid notebooklm-mcp pin format: {token}")
            return token
    raise RuntimeError("NotebookLM MCP args are missing notebooklm-mcp@<version>")


def probe_server(package_pin: str, timeout_seconds: int) -> dict:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("Unable to locate npx/npx.cmd in PATH")
    cmd = [npx, "-y", package_pin, "--help"]
    start = time.time()
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=False,
        timeout=timeout_seconds,
        check=False,
    )
    duration_ms = int((time.time() - start) * 1000)
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "duration_ms": duration_ms,
        "stdout_preview": stdout[:400],
        "stderr_preview": stderr[:400],
    }


def write_selection(notebook_url: str, package_pin: str) -> Path:
    global SELECTION_FILE
    payload = {
        "selected_notebook_url": notebook_url,
        "mcp_package": package_pin,
        "selected_at_unix": int(time.time()),
    }
    try:
        SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SELECTION_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return SELECTION_FILE
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "jarvis-notebooklm" / "notebook_selection.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        SELECTION_FILE = fallback
        return fallback


def main() -> int:
    global SELECTION_FILE

    parser = argparse.ArgumentParser(description="NotebookLM MCP config health-check")
    parser.add_argument("--notebook-url", default=DEFAULT_NOTEBOOK_URL)
    parser.add_argument("--timeout-seconds", type=int, default=25)
    parser.add_argument("--skip-probe", action="store_true", default=False)
    parser.add_argument("--selection-output", type=Path, default=SELECTION_FILE)
    args = parser.parse_args()

    if not URL_PATTERN.match(args.notebook_url):
        raise RuntimeError(f"Notebook URL does not match expected format: {args.notebook_url}")

    server = load_notebooklm_server()
    package_pin = resolve_pinned_package(server.get("args", []))

    probe_result = None
    if not args.skip_probe:
        probe_result = probe_server(package_pin, timeout_seconds=args.timeout_seconds)

    SELECTION_FILE = args.selection_output
    selection_path = write_selection(args.notebook_url, package_pin)

    selection_display = (
        str(selection_path.relative_to(ROOT))
        if selection_path.is_relative_to(ROOT)
        else str(selection_path)
    )

    output = {
        "ok": True,
        "package_pin": package_pin,
        "selection_file": selection_display,
        "probe": probe_result,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        raise SystemExit(1)
