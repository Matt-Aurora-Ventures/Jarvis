# Vanguard Control Board

Standalone control API/UI for Vanguard loop operations.

## Start Runtime Loop

```powershell
powershell -File scripts/start_vanguard_standalone_loop.ps1
```

## Start Control Board

```powershell
python scripts/start_vanguard_control_board.py --host 127.0.0.1 --port 8181
```

Open: `http://127.0.0.1:8181/`

## Auth And Roles

Use one of:

1. API key in `Authorization: Bearer <key>`
2. Signed token (`v1.<payload>.<sig>`) with `role` claim.

Required signed-token claims:

- `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, `role`, `risk_tier`, `scopes`
- required scopes by role:
  - viewer: `vanguard:open`, `vanguard:read`
  - operator/admin: viewer scopes + `vanguard:control`

Role env vars:

- `VANGUARD_VIEWER_API_KEYS`
- `VANGUARD_OPERATOR_API_KEYS`
- `VANGUARD_ADMIN_API_KEYS`
- `VANGUARD_CONTROL_TOKEN_SECRET`

Generate a short-lived signed token:

```powershell
python scripts/generate_vanguard_control_token.py --role operator --ttl-seconds 60
```

Token validation env vars:

- `VANGUARD_CONTROL_TOKEN_ISSUER` (default `jarvis-sniper`)
- `VANGUARD_CONTROL_TOKEN_AUDIENCE` (default `vanguard-control`)
- `VANGUARD_HANDOFF_TOKEN_TTL_SECONDS` (default `60`)
- `VANGUARD_SESSION_TOKEN_TTL_SECONDS` (default `600`)
- `VANGUARD_REPLAY_CACHE_TTL_SECONDS` (default `3600`)

## Public Beta Mode

Default is read-only external posture:

- `VANGUARD_PUBLIC_BETA_MODE=true`
- operator endpoints also require source IP in `VANGUARD_OPERATOR_IP_ALLOWLIST`

Public status endpoint:

- `GET /api/v1/public/status`
- `GET /api/v1/public/health`

## Two-Step Live Arm

1. `POST /api/v1/operator/arm/prepare`
2. `POST /api/v1/operator/arm/confirm` with:
   - `challenge`
   - `phrase` (must match `VANGUARD_ARM_CONFIRM_PHRASE`, default `ARM_LIVE_TRADING`)

Disarm:

- `POST /api/v1/operator/disarm`

When arm state changes, watchdog restarts runner into matching mode.

## Session Handoff Replay Protection

- `POST /api/v1/session/exchange` validates handoff token claims and issuer/audience.
- `jti` is one-time use; replayed tokens are rejected.
- UI launch links can include `?st=<signed_token>` and the page exchanges then removes query params from browser history.

## Guardrails

Configured via env and persisted in control state:

- `PERPS_MAX_TRADES_PER_DAY` (default `40`)
- `PERPS_DAILY_LOSS_LIMIT_USD` (default `500`)

Control state path:

- `PERPS_CONTROL_STATE_PATH`
- default: `<runtime-dir>/control_state.json`

## Secret Management (File-Based Preferred)

For any secret `<NAME>`, prefer file-based loading:

1. `<NAME>_FILE=/secure/path/to/secret`
2. `JARVIS_SECRETS_DIR/<NAME>`
3. `<NAME>` env value

Examples:

- `XAI_API_KEY_FILE`
- `OPENAI_API_KEY_FILE`
- `ANTHROPIC_API_KEY_FILE`
- `TELEGRAM_BOT_TOKEN_FILE`
- `PERPS_SIGNER_KEYPAIR_B58_FILE`

## Reverse Proxy Hardening

Reference hardened NGINX config:

- `deploy/nginx/vanguard_control_hardened.conf`

It includes:

- HTTPS redirect + TLS
- IP allowlist for operator routes
- rate limiting
- optional OAuth2 auth gateway
- security headers
- query-string-free access logging
