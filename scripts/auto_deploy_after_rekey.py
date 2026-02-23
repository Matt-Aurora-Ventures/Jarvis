#!/usr/bin/env python3
"""
Wait for BotFather cooldown rekey to finish, then deploy new tokens/configs.

This is designed to be run in the background on the Windows operator machine.
It does NOT print secrets.

What it deploys:
- KVM8 (jarvis-vps): merges secrets/rekey_jarvis_updates.env into /etc/jarvis/jarvis.env and restarts jarvis-supervisor
- KVM4 (76.13.106.100): updates ClawdBots telegram botToken fields in host-mounted clawdbot.json configs and restarts containers
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "secrets"

META = SECRETS / "rekey_meta.json"
JARVIS_BUNDLE = SECRETS / "rekey_jarvis_updates.env"
CLAWD_BUNDLE = SECRETS / "rekey_clawdbots_updates.env"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _parse_env(path: Path) -> dict[str, str]:
    kv: dict[str, str] = {}
    if not path.exists():
        return kv
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


def _meta_ready(meta: dict) -> bool:
    pending = meta.get("pending") or []
    for p in pending:
        if p.get("reason") == "rate_limited":
            return False
        if p.get("reason") == "missing_bot_rotate_mode":
            return False
    return True


def _clawd_tokens_ready(env: dict[str, str]) -> bool:
    # We consider "ready" when all clawd tokens are present and non-empty.
    required = ["CLAWDJARVIS_BOT_TOKEN", "CLAWDMATT_BOT_TOKEN", "CLAWDFRIDAY_BOT_TOKEN"]
    return all((env.get(k) or "").strip() for k in required)


def deploy_kvm8() -> None:
    if not JARVIS_BUNDLE.exists():
        raise RuntimeError(f"Missing bundle: {JARVIS_BUNDLE}")

    # Copy bundle to VPS and merge into /etc/jarvis/jarvis.env without leaking values.
    _run(["scp", str(JARVIS_BUNDLE), "jarvis-vps:/tmp/rekey_jarvis_updates.env"])
    remote = r"""
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import re

env_path = Path("/etc/jarvis/jarvis.env")
bundle_path = Path("/tmp/rekey_jarvis_updates.env")

def read_env(p: Path):
    if not p.exists():
        return [], {}
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = {}
    for i, line in enumerate(lines):
        s=line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k = s.split("=", 1)[0].strip()
        if k and k not in idx:
            idx[k]=i
    return lines, idx

def read_kv(p: Path):
    kv={}
    if not p.exists():
        return kv
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v=line.split("=",1)
        kv[k.strip()]=v.strip()
    return kv

lines, idx = read_env(env_path)
if not lines:
    lines = ["# Managed by Jarvis rekey deploy", ""]
    idx = {}

updates = read_kv(bundle_path)
for k,v in updates.items():
    line = f"{k}={v}"
    if k in idx:
        lines[idx[k]] = line
    else:
        lines.append(line)
        idx[k] = len(lines)-1

env_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
PY
rm -f /tmp/rekey_jarvis_updates.env
systemctl restart jarvis-supervisor
"""
    _run(["ssh", "jarvis-vps", remote])


def deploy_kvm4(clawd_env: dict[str, str]) -> None:
    # Update the host-mounted clawdbot.json files and restart containers.
    # Paths are from docker inspect mounts on the KVM4 host.
    jarvis_json = "/root/.clawdbot-jarvis/clawdbot.json"
    friday_json = "/root/.clawdbot/clawdbot.json"
    matt_json = "/docker/clawdbot-gateway/config-matt/clawdbot.json"

    # Copy the env bundle to host (optional for future troubleshooting)
    _run(["scp", "-i", str(Path.home() / ".ssh" / "id_ed25519"), str(CLAWD_BUNDLE), "root@76.13.106.100:/tmp/rekey_clawd_updates.env"])

    # Pass *only* container names + paths in the command; tokens are read from /tmp file on-host.
    remote = r"""
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json

bundle = Path("/tmp/rekey_clawd_updates.env")
kv = {}
for raw in bundle.read_text(encoding="utf-8", errors="replace").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k,v = line.split("=",1)
    kv[k.strip()] = v.strip()

def patch(path: Path, token: str) -> None:
    obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    tg = (obj.get("channels") or {}).get("telegram") or {}
    tg["botToken"] = token
    obj.setdefault("channels", {})["telegram"] = tg
    path.write_text(json.dumps(obj, indent=2).rstrip() + "\n", encoding="utf-8")

paths = {
    "jarvis": Path("/root/.clawdbot-jarvis/clawdbot.json"),
    "friday": Path("/root/.clawdbot/clawdbot.json"),
    "matt": Path("/docker/clawdbot-gateway/config-matt/clawdbot.json"),
}

patch(paths["jarvis"], kv.get("CLAWDJARVIS_BOT_TOKEN",""))
patch(paths["friday"], kv.get("CLAWDFRIDAY_BOT_TOKEN",""))
patch(paths["matt"], kv.get("CLAWDMATT_BOT_TOKEN",""))
PY
rm -f /tmp/rekey_clawd_updates.env || true
docker restart clawdbot-jarvis clawdbot-friday clawdbot-matt >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:18888/health >/dev/null || true
"""
    _run(["ssh", "-i", str(Path.home() / ".ssh" / "id_ed25519"), "root@76.13.106.100", remote])


def main() -> int:
    poll_s = int(os.environ.get("REKEY_DEPLOY_POLL_SECONDS", "300"))
    print("[auto-deploy] waiting for rekey to finish...")

    while True:
        if META.exists():
            try:
                meta = json.loads(META.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                meta = {}
        else:
            meta = {}

        clawd_env = _parse_env(CLAWD_BUNDLE)

        if meta and _meta_ready(meta) and _clawd_tokens_ready(clawd_env):
            break

        time.sleep(poll_s)

    print("[auto-deploy] rekey ready; deploying bundles (no secrets printed)...")
    deploy_kvm8()
    deploy_kvm4(clawd_env)
    print("[auto-deploy] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

