#!/usr/bin/env python3
"""Generate short-lived signed control token for Vanguard control board."""

from __future__ import annotations

import argparse
import json
import time
import uuid

from core.jupiter_perps.control_board import _ROLE_SCOPES, _b64url_encode
from core.utils.secret_store import get_secret
import hmac
import hashlib


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate signed control token")
    parser.add_argument("--sub", default="local-operator")
    parser.add_argument("--role", choices=["viewer", "operator", "admin"], default="viewer")
    parser.add_argument("--ttl-seconds", type=int, default=60)
    parser.add_argument("--issuer", default="jarvis-sniper")
    parser.add_argument("--audience", default="vanguard-control")
    parser.add_argument("--risk-tier", default="standard")
    parser.add_argument("--scopes", default="")
    args = parser.parse_args()

    secret = get_secret("VANGUARD_CONTROL_TOKEN_SECRET")
    if not secret:
        raise SystemExit("Missing VANGUARD_CONTROL_TOKEN_SECRET (or _FILE / JARVIS_SECRETS_DIR).")

    scopes = [item.strip() for item in args.scopes.split(",") if item.strip()]
    if not scopes:
        scopes = sorted(_ROLE_SCOPES.get(args.role, _ROLE_SCOPES["viewer"]))

    now = int(time.time())
    payload = {
        "iss": args.issuer,
        "aud": args.audience,
        "sub": args.sub,
        "role": args.role,
        "risk_tier": args.risk_tier,
        "scopes": scopes,
        "iat": now,
        "exp": now + max(60, args.ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    token = f"v1.{payload_b64}.{_b64url_encode(sig)}"
    print(token)


if __name__ == "__main__":
    main()
