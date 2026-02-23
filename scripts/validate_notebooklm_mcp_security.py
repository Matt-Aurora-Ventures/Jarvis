#!/usr/bin/env python3
"""Record NotebookLM MCP package security metadata and audit evidence."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import argparse
import shutil
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG = ROOT / ".mcp.json"
REPORT_PATH = ROOT / "reports" / "security" / "notebooklm_mcp_security.json"
PIN_RE = re.compile(r"^notebooklm-mcp@(\d+\.\d+\.\d+)$")


def load_pin() -> tuple[str, str]:
    cfg = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    args = cfg.get("mcpServers", {}).get("notebooklm", {}).get("args", [])
    for token in args:
        match = PIN_RE.match(token)
        if match:
            return token, match.group(1)
    raise RuntimeError("Pinned notebooklm-mcp version not found in .mcp.json")


def run_json_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, dict | str]:
    executable = cmd[0]
    resolved = shutil.which(executable)
    if resolved is None and os.name == "nt":
        resolved = shutil.which(f"{executable}.cmd")
    if resolved is None:
        raise RuntimeError(f"Required executable not found in PATH: {executable}")
    cmd = [resolved, *cmd[1:]]
    completed = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    text = completed.stdout.strip() or completed.stderr.strip()
    try:
        payload = json.loads(text)
    except Exception:
        payload = text
    return completed.returncode, payload


def fetch_url(url: str) -> dict[str, str | int]:
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-security-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="ignore")
            return {
                "url": url,
                "status": int(resp.status),
                "title": _extract_title(body),
                "contains_no_vuln_phrase": "no direct vulnerabilities" in body.lower(),
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "status": -1,
            "error": str(exc),
        }


def query_osv_npm(package_name: str, version: str) -> dict[str, str | int]:
    payload = json.dumps(
        {
            "package": {"name": package_name, "ecosystem": "npm"},
            "version": version,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "jarvis-security-check/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
            vulns = body.get("vulns", [])
            return {
                "status": int(resp.status),
                "vulnerability_count": len(vulns),
                "first_ids": [item.get("id", "") for item in vulns[:5]],
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": int(exc.code),
            "error": f"HTTPError {exc.code}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": -1,
            "error": str(exc),
        }


def _extract_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return " ".join(match.group(1).split())[:200]


def run_isolated_audit(pin: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="jarvis-nlm-audit-") as tmp:
        temp_path = Path(tmp)
        package_json = {
            "name": "jarvis-notebooklm-audit",
            "private": True,
            "version": "0.0.0",
            "dependencies": {
                "notebooklm-mcp": pin,
            },
        }
        (temp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

        install_rc, install_payload = run_json_cmd(["npm", "install", "--package-lock-only", "--json"], cwd=temp_path)
        audit_rc, audit_payload = run_json_cmd(["npm", "audit", "--json"], cwd=temp_path)

        return {
            "install_returncode": install_rc,
            "install_output": install_payload,
            "audit_returncode": audit_rc,
            "audit_output": audit_payload,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="NotebookLM MCP security metadata collector")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    package_pin, version = load_pin()

    npm_view_rc, npm_view_payload = run_json_cmd(
        ["npm", "view", f"notebooklm-mcp@{version}", "--json"]
    )

    audit = run_isolated_audit(version)
    snyk_page = fetch_url(f"https://security.snyk.io/package/npm/notebooklm-mcp/{version}")
    npm_package_page = fetch_url(f"https://www.npmjs.com/package/notebooklm-mcp/v/{version}")
    osv_query = query_osv_npm("notebooklm-mcp", version)

    report = {
        "generated_at_unix": int(time.time()),
        "package_pin": package_pin,
        "version": version,
        "npm_view_returncode": npm_view_rc,
        "npm_view": npm_view_payload,
        "isolated_audit": audit,
        "third_party_checks": {
            "snyk": snyk_page,
            "npm_package_page": npm_package_page,
            "osv": osv_query,
        },
    }

    output_path = args.output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        output_path = Path(tempfile.gettempdir()) / "jarvis-notebooklm" / "notebooklm_mcp_security.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    report_display = str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path)
    print(json.dumps({"ok": True, "report": report_display}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
