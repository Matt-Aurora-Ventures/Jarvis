"""
Jarvis Full Life Control System.

This is the COMPLETE autonomous control system that can do ANYTHING:
- Google Suite (Gmail, Drive, Calendar, Docs, Sheets)
- Google Cloud (Firebase, Cloud Console, Billing, APIs)
- Servers (SSH, Hostinger, VPS, Deployments)
- Phone Control (via Tailscale to Android)
- Voice Transcription (local Qwen model)
- Website Management
- App Development & Deployment
- Payment Processing
- Full Computer Control

Architecture:
- Browser-based auth (persistent Chrome sessions with saved logins)
- API-based for programmatic access (Google APIs, Firebase Admin)
- SSH for server management
- Tailscale for all device connectivity

Usage:
    from core.automation.life_control import Jarvis

    jarvis = Jarvis()

    # Just ask naturally
    await jarvis.do("Send John an email about tomorrow's meeting")
    await jarvis.do("Deploy the website changes to hostinger")
    await jarvis.do("Create a new Firebase project called MyApp")
    await jarvis.do("Check my Google Cloud billing")
    await jarvis.do("Send a message to my phone")
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================
# SERVICE CONFIGURATIONS
# ============================================

GOOGLE_SERVICES = {
    'gmail': 'https://mail.google.com',
    'drive': 'https://drive.google.com',
    'calendar': 'https://calendar.google.com',
    'docs': 'https://docs.google.com',
    'sheets': 'https://sheets.google.com',
    'slides': 'https://slides.google.com',
    'photos': 'https://photos.google.com',
    'cloud_console': 'https://console.cloud.google.com',
    'firebase': 'https://console.firebase.google.com',
    'billing': 'https://console.cloud.google.com/billing',
    'ai_studio': 'https://aistudio.google.com',
    'colab': 'https://colab.research.google.com',
    'meet': 'https://meet.google.com',
    'chat': 'https://chat.google.com',
    'contacts': 'https://contacts.google.com',
    'keep': 'https://keep.google.com',
    'tasks': 'https://tasks.google.com',
    'play_console': 'https://play.google.com/console',
    'admob': 'https://admob.google.com',
    'analytics': 'https://analytics.google.com',
    'search_console': 'https://search.google.com/search-console',
    'adsense': 'https://www.google.com/adsense',
    'merchant': 'https://merchants.google.com',
    'youtube_studio': 'https://studio.youtube.com',
}

HOSTING_SERVICES = {
    'hostinger': 'https://hpanel.hostinger.com',
    'cloudflare': 'https://dash.cloudflare.com',
    'vercel': 'https://vercel.com/dashboard',
    'netlify': 'https://app.netlify.com',
    'github': 'https://github.com',
}

# Tailscale device IPs
TAILSCALE_DEVICES = {
    'windows': '100.102.41.120',  # kr8tiv
    'vps': '100.124.254.81',      # srv1302498-1
    'phone': '100.88.183.6',      # umidigi-g9c (Android)
}


class VoiceTranscriber:
    """
    Local voice transcription using Qwen/Whisper models.
    """

    def __init__(self, model: str = "qwen"):
        self.model = model
        self._loaded = False

    async def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text."""
        # Use whisper.cpp or faster-whisper for local transcription
        try:
            # Try faster-whisper first
            from faster_whisper import WhisperModel
            if not self._loaded:
                self._model = WhisperModel("base", device="cpu")
                self._loaded = True

            segments, _ = self._model.transcribe(audio_path)
            return " ".join(segment.text for segment in segments)

        except ImportError:
            # Fallback to subprocess whisper
            result = subprocess.run(
                ["whisper", audio_path, "--model", "base", "--output_format", "txt"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip()

    async def transcribe_voice_message(self, telegram_file_path: str) -> str:
        """Transcribe a Telegram voice message."""
        return await self.transcribe(telegram_file_path)


class PhoneController:
    """
    Control Android phone via Tailscale + ADB.
    """

    def __init__(self, phone_ip: str = None):
        self.phone_ip = phone_ip or TAILSCALE_DEVICES.get('phone')

    async def connect(self) -> bool:
        """Connect to phone via ADB over Tailscale."""
        try:
            result = subprocess.run(
                ["adb", "connect", f"{self.phone_ip}:5555"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return "connected" in result.stdout.lower()
        except Exception as e:
            logger.error(f"Phone connection failed: {e}")
            return False

    async def send_notification(self, title: str, message: str) -> bool:
        """Send notification to phone."""
        await self.connect()
        cmd = f'am broadcast -a android.intent.action.MAIN -n com.termux/.app.TermuxActivity --es title "{title}" --es message "{message}"'
        result = subprocess.run(
            ["adb", "-s", f"{self.phone_ip}:5555", "shell", cmd],
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    async def get_battery(self) -> Dict:
        """Get phone battery status."""
        await self.connect()
        result = subprocess.run(
            ["adb", "-s", f"{self.phone_ip}:5555", "shell", "dumpsys", "battery"],
            capture_output=True,
            text=True
        )
        # Parse battery info
        lines = result.stdout.split('\n')
        battery = {}
        for line in lines:
            if 'level:' in line:
                battery['level'] = int(line.split(':')[1].strip())
            elif 'status:' in line:
                battery['status'] = line.split(':')[1].strip()
        return battery

    async def take_screenshot(self, save_path: str) -> bool:
        """Take screenshot on phone and pull it."""
        await self.connect()
        # Take screenshot
        subprocess.run([
            "adb", "-s", f"{self.phone_ip}:5555", "shell",
            "screencap", "-p", "/sdcard/screenshot.png"
        ])
        # Pull to local
        result = subprocess.run([
            "adb", "-s", f"{self.phone_ip}:5555", "pull",
            "/sdcard/screenshot.png", save_path
        ])
        return result.returncode == 0


class ServerManager:
    """
    Manage servers via SSH.
    """

    def __init__(self):
        self.servers = {
            'vps': {
                'host': TAILSCALE_DEVICES['vps'],
                'user': 'root',
            },
            'hostinger': {
                # Add Hostinger SSH details
            }
        }

    async def ssh_command(self, server: str, command: str) -> str:
        """Execute SSH command on server."""
        server_config = self.servers.get(server)
        if not server_config:
            return f"Unknown server: {server}"

        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            f"{server_config['user']}@{server_config['host']}",
            command
        ]

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return f"SSH error: {e}"

    async def deploy_website(self, server: str, path: str) -> str:
        """Deploy website changes."""
        commands = [
            f"cd {path}",
            "git pull origin main",
            "npm install 2>/dev/null || true",
            "npm run build 2>/dev/null || true",
            "systemctl restart nginx 2>/dev/null || service nginx restart 2>/dev/null || true",
        ]
        return await self.ssh_command(server, " && ".join(commands))


class Jarvis:
    """
    The complete autonomous life control system.

    Just tell Jarvis what you want, and it figures out how to do it.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless

        # Components
        self._browser = None
        self._computer = None
        self._voice = VoiceTranscriber()
        self._phone = PhoneController()
        self._servers = ServerManager()

    async def _get_browser(self):
        """Get persistent browser agent."""
        if self._browser is None:
            try:
                from core.automation.browser_agent import BrowserAgent
                self._browser = BrowserAgent(
                    headless=self.headless,
                    persistent_context=True,
                    user_data_dir=os.path.expanduser("~/.jarvis/browser_profile"),
                )
            except ImportError:
                logger.error("browser_agent not available")
        return self._browser

    async def _get_computer(self):
        """Get computer controller."""
        if self._computer is None:
            try:
                from core.automation.computer_control import ComputerController
                self._computer = ComputerController(safe_mode=True)
            except ImportError:
                logger.error("computer_control not available")
        return self._computer

    async def do(self, request: str) -> Dict[str, Any]:
        """
        Execute ANY request. Just describe what you want.

        Examples:
            await jarvis.do("Send John an email about the meeting")
            await jarvis.do("Deploy website to hostinger")
            await jarvis.do("Create a Firebase project")
            await jarvis.do("Check my Google Cloud billing")
            await jarvis.do("Transcribe this voice message")
        """
        request_lower = request.lower()

        # Route to appropriate handler
        if any(x in request_lower for x in ['email', 'gmail', 'mail']):
            return await self._do_google('gmail', request)

        elif any(x in request_lower for x in ['calendar', 'schedule', 'meeting', 'event']):
            return await self._do_google('calendar', request)

        elif any(x in request_lower for x in ['drive', 'docs', 'document', 'sheet', 'spreadsheet']):
            service = 'sheets' if 'sheet' in request_lower else 'drive'
            return await self._do_google(service, request)

        elif any(x in request_lower for x in ['firebase', 'firestore']):
            return await self._do_google('firebase', request)

        elif any(x in request_lower for x in ['cloud', 'gcp', 'billing', 'api']):
            service = 'billing' if 'billing' in request_lower else 'cloud_console'
            return await self._do_google(service, request)

        elif any(x in request_lower for x in ['ai studio', 'gemini', 'vertex']):
            return await self._do_google('ai_studio', request)

        elif any(x in request_lower for x in ['deploy', 'hostinger', 'website', 'server']):
            return await self._do_server(request)

        elif any(x in request_lower for x in ['phone', 'android', 'mobile']):
            return await self._do_phone(request)

        elif any(x in request_lower for x in ['transcribe', 'voice', 'audio']):
            return await self._do_voice(request)

        elif any(x in request_lower for x in ['screenshot', 'screen', 'capture']):
            return await self._do_capture(request)

        elif any(x in request_lower for x in ['file', 'folder', 'download', 'open']):
            return await self._do_computer(request)

        else:
            # Default: try computer control, then browser
            return await self._do_general(request)

    async def _do_google(self, service: str, request: str) -> Dict[str, Any]:
        """Handle Google service requests."""
        browser = await self._get_browser()
        if not browser:
            return {"success": False, "error": "Browser not available"}

        url = GOOGLE_SERVICES.get(service, GOOGLE_SERVICES['drive'])

        task = f"""
Go to {url}

{request}

If you need to log in, use the saved session (should already be logged in).
Report what you did and any results.
"""
        return await browser.run(task)

    async def _do_server(self, request: str) -> Dict[str, Any]:
        """Handle server/deployment requests."""
        request_lower = request.lower()

        if 'hostinger' in request_lower:
            # Use browser for Hostinger panel
            browser = await self._get_browser()
            if browser:
                return await browser.run(
                    f"Go to {HOSTING_SERVICES['hostinger']} and {request}"
                )

        elif 'deploy' in request_lower:
            # SSH deployment
            result = await self._servers.deploy_website('vps', '/var/www/html')
            return {"success": True, "result": result}

        else:
            # General server command
            result = await self._servers.ssh_command('vps', request)
            return {"success": True, "result": result}

    async def _do_phone(self, request: str) -> Dict[str, Any]:
        """Handle phone control requests."""
        request_lower = request.lower()

        if 'battery' in request_lower:
            battery = await self._phone.get_battery()
            return {"success": True, "result": battery}

        elif 'screenshot' in request_lower:
            path = os.path.expanduser("~/Desktop/phone_screenshot.png")
            success = await self._phone.take_screenshot(path)
            return {"success": success, "result": f"Screenshot saved to {path}"}

        elif 'notification' in request_lower or 'send' in request_lower:
            # Extract message
            success = await self._phone.send_notification("Jarvis", request)
            return {"success": success, "result": "Notification sent"}

        return {"success": False, "error": "Unknown phone command"}

    async def _do_voice(self, request: str) -> Dict[str, Any]:
        """Handle voice transcription."""
        # Extract file path from request or use most recent
        # This would typically receive the audio file path
        return {"success": False, "error": "Provide audio file path"}

    async def _do_capture(self, request: str) -> Dict[str, Any]:
        """Handle screenshot/screen capture."""
        computer = await self._get_computer()
        if computer:
            return await computer.execute(
                f"{request}. Save to Desktop and report the file path."
            )
        return {"success": False, "error": "Computer control not available"}

    async def _do_computer(self, request: str) -> Dict[str, Any]:
        """Handle general computer tasks."""
        computer = await self._get_computer()
        if computer:
            return await computer.execute(request)
        return {"success": False, "error": "Computer control not available"}

    async def _do_general(self, request: str) -> Dict[str, Any]:
        """Handle general requests."""
        # Try computer first, then browser
        computer = await self._get_computer()
        if computer:
            result = await computer.execute(request)
            if result.get("success"):
                return result

        browser = await self._get_browser()
        if browser:
            return await browser.run(request)

        return {"success": False, "error": "No handler available"}

    # ========================================
    # CONVENIENCE SHORTCUTS
    # ========================================

    async def email(self, to: str, subject: str, body: str) -> Dict:
        """Send an email."""
        return await self.do(f"Send an email to {to} with subject '{subject}' and body: {body}")

    async def calendar_add(self, title: str, date: str, time: str = None) -> Dict:
        """Add calendar event."""
        time_str = f" at {time}" if time else ""
        return await self.do(f"Create a calendar event '{title}' on {date}{time_str}")

    async def deploy(self, target: str = "hostinger") -> Dict:
        """Deploy website changes."""
        return await self.do(f"Deploy the latest changes to {target}")

    async def create_firebase_project(self, name: str) -> Dict:
        """Create a new Firebase project."""
        return await self.do(f"Create a new Firebase project called '{name}'")

    async def check_billing(self) -> Dict:
        """Check Google Cloud billing."""
        return await self.do("Check my Google Cloud billing and show current charges")


# ========================================
# SINGLETON & CONVENIENCE
# ========================================

_jarvis: Optional[Jarvis] = None


def get_jarvis() -> Jarvis:
    """Get singleton Jarvis instance."""
    global _jarvis
    if _jarvis is None:
        _jarvis = Jarvis()
    return _jarvis


async def do(request: str) -> Dict[str, Any]:
    """
    Quick access to Jarvis.

    Usage:
        from core.automation.life_control import do

        await do("Send an email to John about the project")
        await do("Deploy my website")
        await do("Check my calendar for tomorrow")
    """
    return await get_jarvis().do(request)
