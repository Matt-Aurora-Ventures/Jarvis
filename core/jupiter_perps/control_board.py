"""Standalone Vanguard control API + UI.

Features:
- Public read-only status endpoint for beta sharing
- Authenticated viewer/operator/admin endpoints
- Two-step live arm/disarm workflow
- Runtime loop health + freshness reporting
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.jupiter_perps.live_control import LiveControlConfig, LiveControlState
from core.utils.secret_store import get_secret


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_set(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def _now() -> int:
    return int(time.time())


def _b64url_decode(raw: str) -> bytes:
    padded = raw + "=" * ((4 - (len(raw) % 4)) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class ControlBoardConfig:
    host: str
    port: int
    runtime_dir: Path
    control_state_path: Path
    token_secret: str
    viewer_keys: set[str]
    operator_keys: set[str]
    admin_keys: set[str]
    cors_allowlist: set[str]
    operator_ip_allowlist: set[str]
    public_beta_mode: bool
    api_rate_limit_per_minute: int
    operator_rate_limit_per_minute: int
    token_issuer: str
    token_audience: str
    handoff_token_ttl_seconds: int
    session_token_ttl_seconds: int
    replay_cache_ttl_seconds: int

    @classmethod
    def from_env(cls) -> ControlBoardConfig:
        runtime_dir = Path(
            os.environ.get(
                "JARVIS_RALPH_RUNTIME_DIR",
                str(Path(os.environ.get("LOCALAPPDATA", ".")) / "Jarvis" / "vanguard-standalone"),
            ),
        )
        control_state_path = Path(os.environ.get("PERPS_CONTROL_STATE_PATH", str(runtime_dir / "control_state.json")))
        return cls(
            host=os.environ.get("VANGUARD_CONTROL_HOST", "127.0.0.1"),
            port=int(os.environ.get("VANGUARD_CONTROL_PORT", "8181")),
            runtime_dir=runtime_dir,
            control_state_path=control_state_path,
            token_secret=get_secret("VANGUARD_CONTROL_TOKEN_SECRET"),
            viewer_keys=_parse_csv_set(get_secret("VANGUARD_VIEWER_API_KEYS")),
            operator_keys=_parse_csv_set(get_secret("VANGUARD_OPERATOR_API_KEYS")),
            admin_keys=_parse_csv_set(get_secret("VANGUARD_ADMIN_API_KEYS")),
            cors_allowlist=_parse_csv_set(
                os.environ.get(
                    "VANGUARD_CONTROL_CORS_ALLOWLIST",
                    "https://kr8tiv.web.app,http://localhost:3000,http://127.0.0.1:3000",
                ),
            ),
            operator_ip_allowlist=_parse_csv_set(
                os.environ.get("VANGUARD_OPERATOR_IP_ALLOWLIST", "127.0.0.1,::1,localhost"),
            ),
            public_beta_mode=_env_bool("VANGUARD_PUBLIC_BETA_MODE", True),
            api_rate_limit_per_minute=max(30, int(os.environ.get("VANGUARD_API_RATE_LIMIT_PER_MINUTE", "180"))),
            operator_rate_limit_per_minute=max(5, int(os.environ.get("VANGUARD_OPERATOR_RATE_LIMIT_PER_MINUTE", "30"))),
            token_issuer=os.environ.get("VANGUARD_CONTROL_TOKEN_ISSUER", "jarvis-sniper"),
            token_audience=os.environ.get("VANGUARD_CONTROL_TOKEN_AUDIENCE", "vanguard-control"),
            handoff_token_ttl_seconds=max(60, int(os.environ.get("VANGUARD_HANDOFF_TOKEN_TTL_SECONDS", "60"))),
            session_token_ttl_seconds=max(60, int(os.environ.get("VANGUARD_SESSION_TOKEN_TTL_SECONDS", "600"))),
            replay_cache_ttl_seconds=max(60, int(os.environ.get("VANGUARD_REPLAY_CACHE_TTL_SECONDS", "3600"))),
        )


_ROLE_ORDER = {"viewer": 1, "operator": 2, "admin": 3}
_REQUIRED_TOKEN_CLAIMS = ("iss", "aud", "sub", "exp", "iat", "jti", "role", "risk_tier", "scopes")
_ROLE_SCOPES = {
    "viewer": {"vanguard:open", "vanguard:read"},
    "operator": {"vanguard:open", "vanguard:read", "vanguard:control"},
    "admin": {"vanguard:open", "vanguard:read", "vanguard:control"},
}


def _role_at_least(role: str, minimum: str) -> bool:
    return _ROLE_ORDER.get(role, 0) >= _ROLE_ORDER.get(minimum, 99)


def _audience_matches(raw_aud: Any, expected: str) -> bool:
    if not expected:
        return True
    if isinstance(raw_aud, str):
        return raw_aud == expected
    if isinstance(raw_aud, list):
        return expected in {str(item) for item in raw_aud}
    return False


def _parse_scopes(raw_scopes: Any) -> set[str]:
    if isinstance(raw_scopes, list):
        return {str(item).strip() for item in raw_scopes if str(item).strip()}
    if isinstance(raw_scopes, str):
        return {item.strip() for item in raw_scopes.split() if item.strip()}
    return set()


def _role_scopes(role: str) -> set[str]:
    return set(_ROLE_SCOPES.get(role, _ROLE_SCOPES["viewer"]))


def _redact_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        lowered = key.lower()
        if lowered in {"st", "token", "session_token", "authorization"}:
            redacted[key] = "***REDACTED***"
            continue
        if isinstance(value, dict):
            redacted[key] = _redact_sensitive_dict(value)
            continue
        redacted[key] = value
    return redacted


class _ReplayCache:
    """Persist one-time token IDs (jti) to block replay attacks."""

    def __init__(self, path: Path, ttl_seconds: int) -> None:
        self._path = path
        self._ttl_seconds = max(60, ttl_seconds)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, int]:
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                result: dict[str, int] = {}
                for key, value in loaded.items():
                    if isinstance(key, str):
                        try:
                            result[key] = int(value)
                        except (TypeError, ValueError):
                            continue
                return result
        except Exception:
            pass
        return {}

    def _write(self, data: dict[str, int]) -> None:
        tmp = self._path.with_suffix(f"{self._path.suffix}.tmp")
        tmp.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self._path)

    def _prune(self, data: dict[str, int], now: int) -> dict[str, int]:
        return {k: v for k, v in data.items() if int(v) > now}

    def mark_once(self, jti: str, exp: int) -> bool:
        now = _now()
        data = self._prune(self._read(), now)
        if jti in data:
            return False
        keep_until = max(now + self._ttl_seconds, int(exp or 0))
        data[jti] = keep_until
        self._write(data)
        return True


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes  # noqa: PLC0415

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if handle == 0:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False
    except Exception:
        return False


def _read_pid(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _latest_runner_log(runtime_dir: Path) -> Path | None:
    candidates = sorted(runtime_dir.glob("runner_stderr_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    return candidates[0]


def _extract_recent_events(runtime_dir: Path) -> dict[str, Any]:
    path = _latest_runner_log(runtime_dir)
    heartbeat_ts = 0
    reconcile_ts = 0
    startup_ts = 0
    if path is None:
        return {"heartbeat_ts": 0, "reconcile_ts": 0, "startup_ts": 0}

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-1000:]
    except Exception:
        return {"heartbeat_ts": 0, "reconcile_ts": 0, "startup_ts": 0}

    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        event = payload.get("event")
        ts = int(payload.get("timestamp", 0) or 0)
        if event == "heartbeat":
            heartbeat_ts = max(heartbeat_ts, ts)
        elif event == "reconciliation_cycle":
            reconcile_ts = max(reconcile_ts, ts)
        elif event == "startup":
            startup_ts = max(startup_ts, ts)

    return {"heartbeat_ts": heartbeat_ts, "reconcile_ts": reconcile_ts, "startup_ts": startup_ts}


def _runtime_status(cfg: ControlBoardConfig, live_control: LiveControlState) -> dict[str, Any]:
    runtime_dir = cfg.runtime_dir
    watchdog_pid = _read_pid(runtime_dir / "watchdog.pid")
    runner_pid = _read_pid(runtime_dir / "runner.pid")
    stop_flag = (runtime_dir / "watchdog.stop").exists()

    events = _extract_recent_events(runtime_dir)
    now = _now()
    heartbeat_age = now - events["heartbeat_ts"] if events["heartbeat_ts"] > 0 else None
    reconcile_age = now - events["reconcile_ts"] if events["reconcile_ts"] > 0 else None

    if _pid_running(runner_pid) and heartbeat_age is not None and heartbeat_age <= 30:
        loop_health = "healthy"
    elif _pid_running(runner_pid):
        loop_health = "degraded"
    else:
        loop_health = "down"

    return {
        "runtime_dir": str(runtime_dir),
        "watchdog": {"pid": watchdog_pid, "running": _pid_running(watchdog_pid)},
        "runner": {"pid": runner_pid, "running": _pid_running(runner_pid)},
        "stop_flag_present": stop_flag,
        "loop_health": loop_health,
        "heartbeat_age_seconds": heartbeat_age,
        "reconcile_age_seconds": reconcile_age,
        "last_startup_ts": events["startup_ts"],
        "control": live_control.public_snapshot(),
    }


def _extract_bearer_token(headers: dict[str, str]) -> str:
    auth = headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return ""
    return auth[7:].strip()


def _verify_signed_token(
    token: str,
    secret: str,
    *,
    expected_issuer: str = "",
    expected_audience: str = "",
    required_claims: tuple[str, ...] = (),
    max_ttl_seconds: int = 3600,
) -> dict[str, Any] | None:
    if not secret or "." not in token:
        return None
    parts = token.split(".")
    if len(parts) == 3 and parts[0] == "v1":
        _, payload_b64, sig_b64 = parts
    elif len(parts) == 2:
        payload_b64, sig_b64 = parts
    else:
        return None

    signing_input = payload_b64.encode("ascii")
    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception:
        return None

    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    now = _now()
    exp = int(payload.get("exp", 0) or 0)
    iat = int(payload.get("iat", 0) or 0)
    if exp and exp < now:
        return None
    if iat and iat > now + 60:
        return None
    if iat and exp and exp - iat > max_ttl_seconds:
        return None

    for claim in required_claims:
        if claim not in payload:
            return None

    if expected_issuer and str(payload.get("iss", "")) != expected_issuer:
        return None
    if not _audience_matches(payload.get("aud"), expected_audience):
        return None

    role = str(payload.get("role", "")).lower().strip()
    if role not in _ROLE_ORDER:
        return None
    scopes = _parse_scopes(payload.get("scopes"))
    if not scopes:
        return None
    if not _role_scopes(role).issubset(scopes):
        return None
    return payload


def _authorize(headers: dict[str, str], cfg: ControlBoardConfig) -> tuple[bool, str, str]:
    token = _extract_bearer_token(headers)
    if not token:
        return False, "", "missing_bearer_token"

    if token in cfg.admin_keys:
        return True, "admin", "api_key"
    if token in cfg.operator_keys:
        return True, "operator", "api_key"
    if token in cfg.viewer_keys:
        return True, "viewer", "api_key"

    payload = _verify_signed_token(
        token,
        cfg.token_secret,
        expected_issuer=cfg.token_issuer,
        expected_audience=cfg.token_audience,
        required_claims=_REQUIRED_TOKEN_CLAIMS,
        max_ttl_seconds=max(cfg.handoff_token_ttl_seconds, cfg.session_token_ttl_seconds),
    )
    if payload is None:
        return False, "", "invalid_token"

    role = str(payload.get("role", "viewer")).lower().strip()
    return True, role, str(payload.get("sub", "signed_token"))


def _issue_signed_token(
    secret: str,
    *,
    sub: str,
    role: str,
    issuer: str,
    audience: str,
    ttl_seconds: int = 600,
    scopes: set[str] | None = None,
    risk_tier: str = "standard",
) -> str:
    effective_scopes = sorted(scopes or _role_scopes(role))
    now = _now()
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "role": role,
        "risk_tier": risk_tier,
        "scopes": effective_scopes,
        "iat": now,
        "exp": now + max(60, ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"v1.{payload_b64}.{sig_b64}"


def create_control_board_app(cfg: ControlBoardConfig | None = None):
    try:
        from aiohttp import web
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError("aiohttp is required for control board") from exc

    config = cfg or ControlBoardConfig.from_env()
    live_control = LiveControlState(LiveControlConfig.from_env(str(config.control_state_path)))
    runtime_dir = config.runtime_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)
    audit_log = runtime_dir / "control_audit.log"
    replay_cache = _ReplayCache(runtime_dir / "session_replay_cache.json", config.replay_cache_ttl_seconds)
    rate_book: dict[str, list[int]] = {}

    def _audit(event: str, actor: str, details: dict[str, Any]) -> None:
        entry = {
            "ts": _now(),
            "event": event,
            "actor": actor,
            "details": _redact_sensitive_dict(details),
        }
        with audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def _rate_limit_key(request) -> str:
        return f"{request.remote or 'unknown'}:{request.path}"

    def _check_rate_limit(request, operator: bool = False) -> bool:
        limit = config.operator_rate_limit_per_minute if operator else config.api_rate_limit_per_minute
        now = _now()
        key = _rate_limit_key(request)
        window = rate_book.setdefault(key, [])
        cutoff = now - 60
        window[:] = [ts for ts in window if ts >= cutoff]
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    @web.middleware
    async def security_headers_middleware(request, handler):
        response = await handler(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';"
        )
        return response

    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "")
        if origin and origin in config.cors_allowlist:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    app = web.Application(middlewares=[cors_middleware, security_headers_middleware])

    def _require_role(request, role: str) -> tuple[str, str] | None:
        ok, user_role, actor = _authorize(request.headers, config)
        if not ok or not _role_at_least(user_role, role):
            return None
        return user_role, actor

    def _operator_ip_allowed(request) -> bool:
        remote = (request.remote or "").strip().lower()
        return remote in {ip.lower() for ip in config.operator_ip_allowlist}

    async def index_handler(_request):
        html = _render_control_html(config.public_beta_mode)
        return web.Response(text=html, content_type="text/html")

    async def public_health_handler(_request):
        status = _runtime_status(config, live_control)
        code = 200 if status["loop_health"] in {"healthy", "degraded"} else 503
        return web.json_response(
            {
                "status": status["loop_health"],
                "mode": "live" if status["control"]["desired_live"] else "dry_run",
                "timestamp": _now(),
            },
            status=code,
        )

    async def public_status_handler(request):
        if not _check_rate_limit(request, operator=False):
            return web.json_response({"error": "rate_limited"}, status=429)
        status = _runtime_status(config, live_control)
        return web.json_response(status)

    async def viewer_status_handler(request):
        if not _check_rate_limit(request, operator=False):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "viewer")
        if auth is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response(_runtime_status(config, live_control))

    async def session_exchange_handler(request):
        body = await request.json() if request.can_read_body else {}
        st = ""
        if isinstance(body, dict):
            st = str(body.get("st", "")).strip()
        if not st:
            st = str(request.query.get("st", "")).strip()
        payload = _verify_signed_token(
            st,
            config.token_secret,
            expected_issuer=config.token_issuer,
            expected_audience=config.token_audience,
            required_claims=_REQUIRED_TOKEN_CLAIMS,
            max_ttl_seconds=config.handoff_token_ttl_seconds,
        )
        if payload is None:
            _audit("session_exchange_failed", "anonymous", {"reason": "invalid_or_expired_token"})
            return web.json_response({"error": "invalid_or_expired_token"}, status=401)

        jti = str(payload.get("jti", "")).strip()
        exp = int(payload.get("exp", 0) or 0)
        if not jti or not replay_cache.mark_once(jti, exp):
            _audit("session_exchange_failed", str(payload.get("sub", "unknown")), {"reason": "token_replay", "jti": jti})
            return web.json_response({"error": "token_replay_detected"}, status=401)

        incoming_role = str(payload.get("role", "viewer")).lower().strip()
        incoming_scopes = _parse_scopes(payload.get("scopes"))
        if "vanguard:open" not in incoming_scopes:
            _audit("session_exchange_failed", str(payload.get("sub", "unknown")), {"reason": "missing_scope_vanguard_open"})
            return web.json_response({"error": "missing_scope_vanguard_open"}, status=403)
        if incoming_role not in _ROLE_ORDER:
            incoming_role = "viewer"

        if "vanguard:control" not in incoming_scopes and incoming_role in {"operator", "admin"}:
            incoming_role = "viewer"
        session_scopes = incoming_scopes.intersection(_role_scopes(incoming_role))
        if not session_scopes:
            session_scopes = _role_scopes("viewer")

        session_token = _issue_signed_token(
            config.token_secret,
            sub=str(payload.get("sub", "session")),
            role=incoming_role,
            issuer=config.token_issuer,
            audience=config.token_audience,
            ttl_seconds=config.session_token_ttl_seconds,
            scopes=session_scopes,
            risk_tier=str(payload.get("risk_tier", "standard")),
        )
        _audit(
            "session_exchange_success",
            str(payload.get("sub", "session")),
            {"role": incoming_role, "scopes": sorted(session_scopes), "risk_tier": str(payload.get("risk_tier", "standard"))},
        )
        return web.json_response({"ok": True, "session_token": session_token, "role": incoming_role})

    async def operator_prepare_handler(request):
        if not _check_rate_limit(request, operator=True):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "operator")
        if auth is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        _, actor = auth
        if config.public_beta_mode and not _operator_ip_allowed(request):
            return web.json_response({"error": "operator_ip_not_allowed_in_public_beta"}, status=403)

        data = live_control.prepare_arm(actor=actor)
        _audit("arm_prepare", actor, {"expires_at": data["expires_at"]})
        return web.json_response(data)

    async def operator_confirm_handler(request):
        if not _check_rate_limit(request, operator=True):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "operator")
        if auth is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        _, actor = auth
        if config.public_beta_mode and not _operator_ip_allowed(request):
            return web.json_response({"error": "operator_ip_not_allowed_in_public_beta"}, status=403)

        body = await request.json()
        challenge = str(body.get("challenge", "")).strip()
        phrase = str(body.get("phrase", "")).strip()
        required_phrase = os.environ.get("VANGUARD_ARM_CONFIRM_PHRASE", "ARM_LIVE_TRADING")
        ok, reason, snapshot = live_control.confirm_arm(
            challenge=challenge,
            actor=actor,
            phrase=phrase,
            required_phrase=required_phrase,
        )
        _audit("arm_confirm", actor, {"ok": ok, "reason": reason})
        status = 200 if ok else 400
        return web.json_response({"ok": ok, "reason": reason, "status": snapshot}, status=status)

    async def operator_disarm_handler(request):
        if not _check_rate_limit(request, operator=True):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "operator")
        if auth is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        _, actor = auth
        if config.public_beta_mode and not _operator_ip_allowed(request):
            return web.json_response({"error": "operator_ip_not_allowed_in_public_beta"}, status=403)

        body = await request.json() if request.can_read_body else {}
        reason = str((body or {}).get("reason", "operator_disarm")).strip() if isinstance(body, dict) else "operator_disarm"
        snapshot = live_control.disarm(reason=reason, actor=actor)
        _audit("disarm", actor, {"reason": reason})
        return web.json_response({"ok": True, "status": snapshot})

    async def operator_limits_handler(request):
        if not _check_rate_limit(request, operator=True):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "admin")
        if auth is None:
            return web.json_response({"error": "unauthorized_admin_required"}, status=401)
        _, actor = auth
        if config.public_beta_mode and not _operator_ip_allowed(request):
            return web.json_response({"error": "operator_ip_not_allowed_in_public_beta"}, status=403)

        body = await request.json()
        max_trades = body.get("max_trades_per_day")
        daily_loss = body.get("daily_loss_limit_usd")
        snapshot = live_control.set_limits(
            max_trades_per_day=int(max_trades) if max_trades is not None else None,
            daily_loss_limit_usd=float(daily_loss) if daily_loss is not None else None,
        )
        _audit(
            "limits_update",
            actor,
            {
                "max_trades_per_day": snapshot["limits"]["max_trades_per_day"],
                "daily_loss_limit_usd": snapshot["limits"]["daily_loss_limit_usd"],
            },
        )
        return web.json_response({"ok": True, "status": snapshot})

    async def operator_audit_handler(request):
        if not _check_rate_limit(request, operator=True):
            return web.json_response({"error": "rate_limited"}, status=429)
        auth = _require_role(request, "operator")
        if auth is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        if not audit_log.exists():
            return web.json_response({"events": []})
        lines = audit_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return web.json_response({"events": events})

    app.router.add_get("/", index_handler)
    app.router.add_get("/api/v1/public/health", public_health_handler)
    app.router.add_get("/api/v1/public/status", public_status_handler)
    app.router.add_get("/api/v1/viewer/status", viewer_status_handler)
    app.router.add_post("/api/v1/session/exchange", session_exchange_handler)
    app.router.add_post("/api/v1/operator/arm/prepare", operator_prepare_handler)
    app.router.add_post("/api/v1/operator/arm/confirm", operator_confirm_handler)
    app.router.add_post("/api/v1/operator/disarm", operator_disarm_handler)
    app.router.add_post("/api/v1/operator/limits", operator_limits_handler)
    app.router.add_get("/api/v1/operator/audit", operator_audit_handler)
    app.router.add_options("/{tail:.*}", lambda _request: web.Response(status=204))

    return app


def _render_control_html(public_beta_mode: bool) -> str:
    badge = "PUBLIC BETA (read-only external)" if public_beta_mode else "PRIVATE OPERATOR MODE"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vanguard Control Board</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto; margin: 24px; background:#0b1116; color:#d7e1ea; }}
    .card {{ background:#14202b; border:1px solid #25384a; border-radius:10px; padding:16px; margin-bottom:16px; }}
    .row {{ display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap; }}
    button {{ background:#2a6df5; color:white; border:0; padding:8px 12px; border-radius:8px; cursor:pointer; }}
    button.secondary {{ background:#38485a; }}
    input {{ background:#0e1821; color:#d7e1ea; border:1px solid #2a3c4d; padding:8px; border-radius:8px; min-width:280px; }}
    pre {{ background:#0e1821; border:1px solid #2a3c4d; border-radius:8px; padding:12px; overflow:auto; }}
    .pill {{ display:inline-block; padding:4px 8px; border-radius:999px; background:#1f3344; border:1px solid #2a4a61; }}
  </style>
</head>
<body>
  <h1>Vanguard Control Board</h1>
  <p><span class="pill">{badge}</span></p>
  <p><span id="sessionState" class="pill">connected as anonymous</span></p>
  <div class="card">
    <div class="row">
      <button onclick="refreshPublic()">Refresh Public Status</button>
      <button class="secondary" onclick="refreshViewer()">Refresh Viewer Status</button>
    </div>
    <pre id="status">loading...</pre>
  </div>
  <div class="card">
    <h3>Operator Actions</h3>
    <div class="row"><input id="token" placeholder="Bearer token or API key" /></div>
    <div class="row"><input id="challenge" placeholder="Challenge from prepare" /></div>
    <div class="row"><input id="phrase" placeholder="Arm confirmation phrase" /></div>
    <div class="row">
      <button onclick="prepareArm()">Prepare Arm</button>
      <button onclick="confirmArm()">Confirm Arm</button>
      <button class="secondary" onclick="disarm()">Disarm</button>
    </div>
    <pre id="operator">operator output...</pre>
  </div>
  <script>
    function setSessionState(text) {{
      document.getElementById("sessionState").textContent = text;
    }}
    function authHeaders() {{
      const token = document.getElementById("token").value.trim();
      const h = {{"Content-Type":"application/json"}};
      if (token) h["Authorization"] = "Bearer " + token;
      return h;
    }}
    async function refreshPublic() {{
      const r = await fetch("/api/v1/public/status");
      const j = await r.json();
      document.getElementById("status").textContent = JSON.stringify(j, null, 2);
    }}
    async function refreshViewer() {{
      const r = await fetch("/api/v1/viewer/status", {{ headers: authHeaders() }});
      const j = await r.json();
      document.getElementById("status").textContent = JSON.stringify(j, null, 2);
    }}
    async function prepareArm() {{
      const r = await fetch("/api/v1/operator/arm/prepare", {{ method:"POST", headers: authHeaders(), body: "{{}}" }});
      const j = await r.json();
      if (j.challenge) document.getElementById("challenge").value = j.challenge;
      document.getElementById("operator").textContent = JSON.stringify(j, null, 2);
    }}
    async function confirmArm() {{
      const payload = {{ challenge: document.getElementById("challenge").value.trim(), phrase: document.getElementById("phrase").value.trim() }};
      const r = await fetch("/api/v1/operator/arm/confirm", {{ method:"POST", headers: authHeaders(), body: JSON.stringify(payload) }});
      const j = await r.json();
      document.getElementById("operator").textContent = JSON.stringify(j, null, 2);
    }}
    async function disarm() {{
      const r = await fetch("/api/v1/operator/disarm", {{ method:"POST", headers: authHeaders(), body: JSON.stringify({{reason:"ui_disarm"}}) }});
      const j = await r.json();
      document.getElementById("operator").textContent = JSON.stringify(j, null, 2);
    }}
    async function exchangeFromQuery() {{
      const params = new URLSearchParams(window.location.search);
      const st = params.get("st");
      if (!st) {{
        return;
      }}
      const r = await fetch("/api/v1/session/exchange", {{
        method: "POST",
        headers: {{"Content-Type":"application/json"}},
        body: JSON.stringify({{ st }})
      }});
      const j = await r.json();
      if (j.session_token) {{
        document.getElementById("token").value = j.session_token;
        setSessionState("connected as " + (j.role || "viewer"));
      }} else {{
        setSessionState("session handoff failed");
      }}
      const cleanUrl = window.location.origin + window.location.pathname;
      window.history.replaceState({{}}, "", cleanUrl);
      document.getElementById("operator").textContent = JSON.stringify(j, null, 2);
    }}
    exchangeFromQuery();
    refreshPublic();
  </script>
</body>
</html>
"""

