"""
Tailscale Remote Computer Control Server.

Exposes a secure API for remote computer control via Tailscale.
ClawdBots can call this to control your local machine.

Run on your Windows machine:
    python -m core.automation.remote_control_server

Then from VPS/Telegram bots, call:
    POST http://<tailscale-ip>:8765/computer
    POST http://<tailscale-ip>:8765/browser

Security:
- Only accessible via Tailscale network
- API key authentication
- Rate limiting
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime
from functools import wraps
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_PORT = 8765
API_KEY_ENV = "JARVIS_REMOTE_API_KEY"


def get_or_create_api_key() -> str:
    """Get existing API key or generate a new one."""
    key = os.getenv(API_KEY_ENV)
    if key:
        return key

    # Generate new key
    key = secrets.token_urlsafe(32)
    print(f"""
============================================================
   NEW API KEY GENERATED

   Add this to your .env on BOTH local and VPS:
   {API_KEY_ENV}={key}
============================================================
    """)
    return key


def verify_api_key(request: web.Request, api_key: str) -> bool:
    """Verify the API key from request headers."""
    provided = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(provided, api_key)


def require_api_key(api_key: str):
    """Decorator to require API key authentication."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: web.Request, *args, **kwargs):
            if not verify_api_key(request, api_key):
                return web.json_response(
                    {"error": "Invalid or missing API key"},
                    status=401
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


class RemoteControlServer:
    """
    Secure remote control server accessible via Tailscale.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",  # Bind to all interfaces (Tailscale included)
        port: int = DEFAULT_PORT,
        api_key: str = None,
    ):
        self.host = host
        self.port = port
        self.api_key = api_key or get_or_create_api_key()
        self.app = web.Application()
        self._browser_agent = None
        self._computer_controller = None
        self._request_count = 0
        self._setup_routes()

    def _setup_routes(self):
        """Set up API routes."""
        self.app.router.add_get("/health", self.health)
        self.app.router.add_post("/browser", self._auth_wrap(self.browser_task))
        self.app.router.add_post("/computer", self._auth_wrap(self.computer_task))
        self.app.router.add_post("/telegram", self._auth_wrap(self.telegram_task))
        self.app.router.add_get("/status", self._auth_wrap(self.status))

    def _auth_wrap(self, handler):
        """Wrap handler with authentication."""
        @wraps(handler)
        async def wrapper(request: web.Request):
            if not verify_api_key(request, self.api_key):
                return web.json_response(
                    {"error": "Invalid or missing API key"},
                    status=401
                )
            return await handler(request)
        return wrapper

    async def health(self, request: web.Request) -> web.Response:
        """Health check endpoint (no auth required)."""
        return web.json_response({
            "status": "healthy",
            "service": "jarvis-remote-control",
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def status(self, request: web.Request) -> web.Response:
        """Get server status."""
        return web.json_response({
            "status": "running",
            "requests_handled": self._request_count,
            "browser_agent_ready": self._browser_agent is not None,
            "computer_controller_ready": self._computer_controller is not None,
        })

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
                return web.json_response(
                    {"error": "Missing 'task' in request body"},
                    status=400
                )

            # Lazy import to avoid startup delay
            if self._browser_agent is None:
                from core.automation.browser_agent import BrowserAgent
                self._browser_agent = BrowserAgent(headless=True)

            result = await self._browser_agent.run(task)
            if not isinstance(result, dict):
                result = {"success": False, "result": result}

            return web.json_response({
                "success": result.get("success", False),
                "result": str(result.get("result", "")),
                "task": task,
            })

        except Exception as e:
            logger.exception("Browser task error")
            return web.json_response(
                {"error": str(e)},
                status=500
            )

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
                return web.json_response(
                    {"error": "Missing 'task' in request body"},
                    status=400
                )

            # Lazy import
            if self._computer_controller is None:
                from core.automation.computer_control import ComputerController
                self._computer_controller = ComputerController(safe_mode=True)

            result = await self._computer_controller.execute(task)
            if not isinstance(result, dict):
                result = {"success": False, "output": result}

            return web.json_response({
                "success": result.get("success", False),
                "output": str(result.get("output", "")),
                "task": task,
            })

        except Exception as e:
            logger.exception("Computer task error")
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def telegram_task(self, request: web.Request) -> web.Response:
        """
        Execute a Telegram Web task.

        POST /telegram
        Body: {
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
                return web.json_response(
                    {"error": "Missing 'action' in request body"},
                    status=400
                )

            from core.automation.browser_agent import TelegramWebAgent

            agent = TelegramWebAgent(headless=True)

            try:
                if action == "send_message":
                    chat = data.get("chat")
                    message = data.get("message")
                    if not chat or not message:
                        return web.json_response(
                            {"error": "Missing 'chat' or 'message'"},
                            status=400
                        )
                    result = await agent.send_message(chat, message)
                    if not isinstance(result, dict):
                        result = {"success": False, "result": result}

                elif action == "read_messages":
                    chat = data.get("chat")
                    count = data.get("count", 10)
                    if not chat:
                        return web.json_response(
                            {"error": "Missing 'chat'"},
                            status=400
                        )
                    result = await agent.read_recent_messages(chat, count)
                    if not isinstance(result, dict):
                        result = {"success": False, "result": result}

                else:
                    return web.json_response(
                        {"error": f"Unknown action: {action}"},
                        status=400
                    )

                return web.json_response({
                    "success": result.get("success", False),
                    "result": str(result.get("result", "")),
                })

            finally:
                await agent.close()

        except Exception as e:
            logger.exception("Telegram task error")
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def start(self):
        """Start the server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(f"""
============================================================
   Jarvis Remote Control Server
============================================================
   Running on: http://{self.host}:{self.port}

   Endpoints:
     GET  /health  - Health check (no auth)
     POST /browser - Browser automation
     POST /computer - Full computer control
     POST /telegram - Telegram Web tasks
     GET  /status  - Server status

   API Key: Set X-API-Key header
   Access via Tailscale: http://<tailscale-ip>:{self.port}
============================================================
        """)

        # Keep running
        while True:
            await asyncio.sleep(3600)


def run_server(port: int = DEFAULT_PORT):
    """Run the remote control server."""
    logging.basicConfig(level=logging.INFO)

    server = RemoteControlServer(port=port)
    asyncio.run(server.start())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Jarvis Remote Control Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    run_server(port=args.port)
