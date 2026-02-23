#!/usr/bin/env python3
"""
Seed Supermemory with local markdown memory files (idempotent via customId).

This is designed to run inside the clawdbot-golden container at boot time.

Sources (if they exist):
- /root/clawd/MEMORY.md
- /root/clawd/memory/*.md
- /root/.clawdbot/MEMORY.md
- /root/.clawdbot/memory/*.md

Environment:
- SUPERMEMORY_API_KEY (or SUPERMEMORY_OPENCLAW_API_KEY)
- SUPERMEMORY_CONTAINER_TAG (defaults to kr8tiv_<bot>)
- SUPERMEMORY_SHARED_TAG (defaults to kr8tiv_shared)
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import sys
import time
import urllib.error
import urllib.request
import base64
from dataclasses import dataclass
from pathlib import Path


API_BASE = "https://api.supermemory.ai"

# Supermemory request integrity headers used by the official SDK/plugins.
# Without these headers, the API may respond with 403 (e.g., HTML block page).
_INTEGRITY_VERSION = 1
_INTEGRITY_HMAC_KEY = "7f2a9c4b8e1d6f3a5c0b9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _b64url_no_pad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _integrity_headers(api_key: str, container_tag: str) -> dict[str, str]:
    api_hash = _sha256_hex(api_key)
    tag_hash = _sha256_hex(container_tag)
    msg = f"{api_hash}:{tag_hash}:{_INTEGRITY_VERSION}"
    sig = hmac.new(_INTEGRITY_HMAC_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return {
        "X-Content-Hash": tag_hash,
        "X-Request-Integrity": f"v{_INTEGRITY_VERSION}.{_b64url_no_pad(sig)}",
    }


@dataclass(frozen=True)
class Doc:
    path: Path
    content: str


def _post_json(url: str, api_key: str, payload: dict, extra_headers: dict[str, str] | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        return int(getattr(e, "code", 0) or 0), body


def _discover_sources() -> list[Path]:
    candidates: list[Path] = []
    for root in [Path("/root/clawd"), Path("/root/.clawdbot")]:
        candidates.append(root / "MEMORY.md")
        candidates.extend(sorted((root / "memory").glob("*.md")))
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        out.append(p)
    return [p for p in out if p.exists() and p.is_file()]


def main() -> int:
    api_key = os.environ.get("SUPERMEMORY_API_KEY") or os.environ.get("SUPERMEMORY_OPENCLAW_API_KEY")
    if not api_key:
        print("[supermemory-seed] SUPERMEMORY_API_KEY not set; skipping")
        return 0

    bot_name = (os.environ.get("BOT_NAME") or "unknown").strip().lower()
    private_tag = (os.environ.get("SUPERMEMORY_CONTAINER_TAG") or f"kr8tiv_{bot_name}").strip()
    integrity = _integrity_headers(api_key, private_tag)

    sources = _discover_sources()
    if not sources:
        print("[supermemory-seed] no local memory markdown found; nothing to seed")
        return 0

    ok = 0
    fail = 0
    for p in sources:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            fail += 1
            print(f"[supermemory-seed] read failed: {p}: {e}")
            continue

        if not content.strip():
            continue

        # Make idempotent per file path (so reruns update-in-place).
        custom_id = f"{private_tag}:{p}"
        payload = {
            "content": content,
            "containerTag": private_tag,
            "customId": custom_id,
            "metadata": {
                "source": "disk_seed",
                "bot": bot_name,
                "path": str(p),
                "kind": "markdown_memory",
                "seeded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

        status, body = _post_json(f"{API_BASE}/v3/documents", api_key, payload, extra_headers=integrity)
        if 200 <= status < 300:
            ok += 1
            continue

        fail += 1
        # Avoid dumping full response bodies (may contain echoed content).
        preview = (body or "").replace("\n", " ")[:240]
        print(f"[supermemory-seed] upload failed: {p} status={status} body={preview}")

    print(f"[supermemory-seed] done: ok={ok} fail={fail} tag={private_tag}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
