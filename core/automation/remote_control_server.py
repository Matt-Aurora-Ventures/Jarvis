"""
Tailscale Remote Computer Control Server.

This exposes an HTTP API for remote computer control (browser + OS actions).

Security defaults:
- Requires `JARVIS_REMOTE_API_KEY` (refuses to start without it).
- Binds to `127.0.0.1` by default (no LAN exposure).
- Enforces an IP allowlist by default: localhost + Tailscale CIDRs.
- Supports a repo-root pause flag file: `PAUSE_AUTOMATIONS`.

Run on Windows:
    set JARVIS_REMOTE_API_KEY=...
    python -m core.automation.remote_control_server --host 127.0.0.1 --port 8765

To allow access from your Tailnet (explicit opt-in):
    python -m core.automation.remote_control_server --host <tailscale-ip> --port 8765
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import logging
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Iterable, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
API_KEY_ENV = "JARVIS_REMOTE_API_KEY"

_TAILSCALE_CIDRS = (
    # Tailscale IPv4 range (CGNAT)
    "100.64.0.0/10",
    # Tailscale IPv6 ULA range (default)
    "fd7a:115c:a1e0::/48",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _project_root() -> Path:
    # core/automation/remote_control_server.py -> core/automation -> core -> repo root
    return Path(__file__).resolve().parents[2]


def _pause_flag_path() -> Path:
    return _project_root() / "PAUSE_AUTOMATIONS"


def automations_paused() -> bool:
    return _pause_flag_path().exists() or _truthy(os.getenv("JARVIS_PAUSE_AUTOMATIONS"))


def get_api_key_or_raise() -> str:
    key = os.getenv(API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set. Refusing to start remote control server."
        )
    return key


def verify_api_key(request: web.Request, api_key: str) -> bool:
    provided = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(provided, api_key)


def _parse_allowed_networks(extra_cidrs: Optional[Iterable[str]]) -> list[ipaddress._BaseNetwork]:
    cidrs: list[str] = [
        "127.0.0.1/32",
        "::1/128",
        *_TAILSCALE_CIDRS,
    ]

    env_extra = os.getenv("JARVIS_REMOTE_ALLOW_CIDRS", "").strip()
    if env_extra:
        for part in env_extra.split(","):
            part = part.strip()
            if part:
                cidrs.append(part)

    if extra_cidrs:
        cidrs.extend([c for c in extra_cidrs if c])

    nets: list[ipaddress._BaseNetwork] = []
    for c in cidrs:
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid CIDR in allowlist: %r", c)
    return nets


def _remote_ip(request: web.Request) -> Optional[ipaddress._BaseAddress]:
    remote = request.remote
    if not remote:
        return None

    # Strip IPv6 zone index if present (e.g. "fe80::1%12").
    remote = remote.split("%", 1)[0]

    try:
        ip = ipaddress.ip_address(remote)
    except ValueError:
        return None

    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


class RemoteControlServer:
    """
    Remote control server.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        api_key: Optional[str] = None,
        allow_any_client: bool = False,
        allowed_cidrs: Optional[Iterable[str]] = None,
    ):
        self.host = host
        self.port = port
        self.api_key = api_key or get_api_key_or_raise()
        self.allow_any_client = allow_any_client
        self.allowed_networks = _parse_allowed_networks(allowed_cidrs)

        self.app = web.Application()
        self._browser_agent = None
        self._computer_controller = None
        self._request_count = 0
        self._setup_routes()

    def _client_allowed(self, request: web.Request) -> bool:
        if self.allow_any_client:
            return True

        ip = _remote_ip(request)
        if ip is None:
            return False
        return any(ip in net for net in self.allowed_networks)

    def _precheck(self, request: web.Request) -> Optional[web.Response]:
        if automations_paused():
            return web.json_response(
                {"error": "Automations paused (PAUSE_AUTOMATIONS is set)"},
                status=503,
            )
        if not self._client_allowed(request):
            return web.json_response({"error": "Client not allowed"}, status=403)
        return None

    def _wrap_public(self, handler):
        @wraps(handler)
        async def wrapper(request: web.Request):
            pre = self._precheck(request)
            if pre is not None:
                return pre
            return await handler(request)

        return wrapper

    def _wrap_authed(self, handler):
        @wraps(handler)
        async def wrapper(request: web.Request):
            pre = self._precheck(request)
            if pre is not None:
                return pre
            if not verify_api_key(request, self.api_key):
                return web.json_response(
                    {"error": "Invalid or missing API key"},
                    status=401,
                )
            return await handler(request)

        return wrapper

    def _setup_routes(self):
        self.app.router.add_get("/health", self._wrap_public(self.health))
        self.app.router.add_get("/status", self._wrap_authed(self.status))
        self.app.router.add_post("/browser", self._wrap_authed(self.browser_task))
        self.app.router.add_post("/computer", self._wrap_authed(self.computer_task))
        self.app.router.add_post("/telegram", self._wrap_authed(self.telegram_task))

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "healthy",
                "service": "jarvis-remote-control",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "running",
                "requests_handled": self._request_count,
                "browser_agent_ready": self._browser_agent is not None,
                "computer_controller_ready": self._computer_controller is not None,
            }
        )

    async def browser_task(self, request: web.Request) -> web.Response:
        """
        Execute a browser automation task.

        POST /browser
        Body: {"task": "Go to google.com and search for 'solana'"}
        """
        self._request_count += 1

        try:
            data = await request.json()
            task = data.get("task")
            if not task:
                return web.json_response({"error": "Missing 'task' in request body"}, status=400)

            if self._browser_agent is None:
                from core.automation.browser_agent import BrowserAgent

                self._browser_agent = BrowserAgent(headless=True)

            result = await self._browser_agent.run(task)
            if not isinstance(result, dict):
                result = {"success": False, "result": result}

            return web.json_response(
                {
                    "success": bool(result.get("success", False)),
                    "result": str(result.get("result", "")),
                    "task": task,
                }
            )
        except Exception as e:
            logger.exception("Browser task error")
            return web.json_response({"error": str(e)}, status=500)

    async def computer_task(self, request: web.Request) -> web.Response:
        """
        Execute a full computer control task.

        POST /computer
        Body: {"task": "Create a file called hello.txt on the desktop"}
        """
        self._request_count += 1

        try:
            data = await request.json()
            task = data.get("task")
            if not task:
                return web.json_response({"error": "Missing 'task' in request body"}, status=400)

            if self._computer_controller is None:
                from core.automation.computer_control import ComputerController

                self._computer_controller = ComputerController(safe_mode=True)

            result = await self._computer_controller.execute(task)
            if not isinstance(result, dict):
                result = {"success": False, "output": result}

            return web.json_response(
                {
                    "success": bool(result.get("success", False)),
                    "output": str(result.get("output", "")),
                    "task": task,
                }
            )
        except Exception as e:
            logger.exception("Computer task error")
            return web.json_response({"error": str(e)}, status=500)

    async def telegram_task(self, request: web.Request) -> web.Response:
        """
        Execute a Telegram Web task.

        POST /telegram
        Body:
            {
              "action": "send_message",
              "chat": "Saved Messages",
              "message": "Hello from remote!"
            }
        """
        self._request_count += 1

        try:
            data = await request.json()
            action = data.get("action")
            if not action:
                return web.json_response({"error": "Missing 'action' in request body"}, status=400)

            from core.automation.browser_agent import TelegramWebAgent

            agent = TelegramWebAgent(headless=True)
            try:
                if action == "send_message":
                    chat = data.get("chat")
                    message = data.get("message")
                    if not chat or not message:
                        return web.json_response({"error": "Missing 'chat' or 'message'"}, status=400)
                    result = await agent.send_message(chat, message)
                    if not isinstance(result, dict):
                        result = {"success": False, "result": result}
                elif action == "read_messages":
                    chat = data.get("chat")
                    count = data.get("count", 10)
                    if not chat:
                        return web.json_response({"error": "Missing 'chat'"}, status=400)
                    result = await agent.read_recent_messages(chat, count)
                    if not isinstance(result, dict):
                        result = {"success": False, "result": result}
                else:
                    return web.json_response({"error": f"Unknown action: {action}"}, status=400)

                return web.json_response(
                    {
                        "success": bool(result.get("success", False)),
                        "result": str(result.get("result", "")),
                    }
                )
            finally:
                await agent.close()
        except Exception as e:
            logger.exception("Telegram task error")
            return web.json_response({"error": str(e)}, status=500)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(
            "\n".join(
                [
                    "=" * 60,
                    "Jarvis Remote Control Server",
                    "=" * 60,
                    f"Running on: http://{self.host}:{self.port}",
                    f"Allowed networks: {', '.join(str(n) for n in self.allowed_networks)}"
                    if not self.allow_any_client
                    else "Allowed networks: ANY (unsafe)",
                    "",
                    "Endpoints:",
                    "  GET  /health   (no auth, allowlisted)",
                    "  GET  /status   (auth)",
                    "  POST /browser  (auth)",
                    "  POST /computer (auth)",
                    "  POST /telegram (auth)",
                    "",
                    "Auth header: X-API-Key: <JARVIS_REMOTE_API_KEY>",
                    "=" * 60,
                ]
            )
        )

        while True:
            await asyncio.sleep(3600)


def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allow_any_client: bool = False,
    allowed_cidrs: Optional[Iterable[str]] = None,
):
    logging.basicConfig(level=logging.INFO)

    if automations_paused():
        print(f"[Jarvis] Automations paused. Refusing to start remote control server. ({_pause_flag_path()})")
        return

    server = RemoteControlServer(
        host=host,
        port=port,
        allow_any_client=allow_any_client,
        allowed_cidrs=allowed_cidrs,
    )
    asyncio.run(server.start())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis Remote Control Server")
    parser.add_argument("--host", type=str, default=os.getenv("JARVIS_REMOTE_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("JARVIS_REMOTE_PORT", str(DEFAULT_PORT))))
    parser.add_argument(
        "--allow-any-client",
        action="store_true",
        help="Disable IP allowlist checks (unsafe; use only if you know what you're doing).",
    )
    parser.add_argument(
        "--allow-cidr",
        action="append",
        default=[],
        help="Additional allowed CIDR(s). Can be specified multiple times.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parse_args()
        run_server(
            host=args.host,
            port=args.port,
            allow_any_client=bool(args.allow_any_client),
            allowed_cidrs=args.allow_cidr,
        )
    except RuntimeError as exc:
        print(f"[Jarvis] ERROR: {exc}")
        raise SystemExit(2)
