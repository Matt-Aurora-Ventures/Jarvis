"""
JARVIS System Tray - Lightweight Always-On Desktop Presence

Uses pystray (cross-platform) for minimal resource usage.
Provides quick access to JARVIS features without a heavy GUI.

Dependencies: pip install pystray pillow
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
import webbrowser

# Type checking imports
if TYPE_CHECKING:
    from PIL import Image as PILImage

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    pystray = None
    Image = None
    ImageDraw = None

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "tray_state.json"
ICON_PATH = ROOT / "assets" / "jarvis_icon.png"


@dataclass
class TrayState:
    """Persistent state for system tray."""
    voice_enabled: bool = False
    daemon_running: bool = False
    last_activity: str = ""
    pending_notifications: List[str] = field(default_factory=list)
    quick_actions: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'voice_enabled': self.voice_enabled,
                'daemon_running': self.daemon_running,
                'last_activity': self.last_activity,
                'pending_notifications': self.pending_notifications[-10:],
                'quick_actions': self.quick_actions[-5:],
                'stats': self.stats,
            }, f, indent=2)

    @classmethod
    def load(cls) -> 'TrayState':
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                return cls(**data)
            except Exception:
                pass
        return cls()


class JarvisSystemTray:
    """
    Lightweight system tray for JARVIS.

    Features:
    - Status indicator (green/yellow/red)
    - Voice toggle
    - Quick command access
    - Notification popup
    - Open dashboard/telegram
    - Resource monitoring
    """

    def __init__(self):
        if not PYSTRAY_AVAILABLE:
            logger.warning("pystray not available. Install: pip install pystray pillow")
            return

        self.state = TrayState.load()
        self.icon = None  # pystray.Icon when available
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Callbacks for external integration
        self.on_voice_toggle: Optional[Callable[[bool], None]] = None
        self.on_command: Optional[Callable[[str], None]] = None
        self.on_research: Optional[Callable[[str], None]] = None

        # Status colors
        self._status = "idle"  # idle, active, error, listening

    def _create_icon_image(self, status: str = "idle") -> "PILImage.Image":
        """Create dynamic icon based on status."""
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Status colors
        colors = {
            'idle': '#4A90D9',      # Blue - idle
            'active': '#2ECC71',    # Green - processing
            'listening': '#9B59B6', # Purple - voice active
            'error': '#E74C3C',     # Red - error
            'warning': '#F39C12',   # Orange - warning
        }
        color = colors.get(status, colors['idle'])

        # Draw circle with status color
        padding = 4
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=color,
            outline='#2C3E50',
            width=2
        )

        # Draw "J" in center
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()

        text = "J"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - 4
        draw.text((x, y), text, fill='white', font=font)

        return img

    def _build_menu(self):
        """Build dynamic context menu."""
        voice_text = "Voice: ON" if self.state.voice_enabled else "Voice: OFF"
        daemon_text = "Daemon: Running" if self.state.daemon_running else "Daemon: Stopped"

        return pystray.Menu(
            pystray.MenuItem(
                f"JARVIS - {self._status.upper()}",
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,

            # Voice toggle
            pystray.MenuItem(
                voice_text,
                self._toggle_voice,
                checked=lambda item: self.state.voice_enabled
            ),

            # Daemon status
            pystray.MenuItem(daemon_text, None, enabled=False),

            pystray.Menu.SEPARATOR,

            # Quick actions submenu
            pystray.MenuItem(
                "Quick Actions",
                pystray.Menu(
                    pystray.MenuItem("Run Sentiment Report", lambda: self._run_action("sentiment")),
                    pystray.MenuItem("Check Wallet", lambda: self._run_action("wallet")),
                    pystray.MenuItem("Research Mode", lambda: self._run_action("research")),
                    pystray.MenuItem("System Status", lambda: self._run_action("status")),
                )
            ),

            # Open links
            pystray.MenuItem(
                "Open",
                pystray.Menu(
                    pystray.MenuItem("Telegram Bot", lambda: self._open_link("telegram")),
                    pystray.MenuItem("Dashboard", lambda: self._open_link("dashboard")),
                    pystray.MenuItem("GitHub", lambda: self._open_link("github")),
                )
            ),

            pystray.Menu.SEPARATOR,

            # Stats
            pystray.MenuItem(
                f"Last: {self.state.last_activity[:30] if self.state.last_activity else 'None'}",
                None,
                enabled=False
            ),

            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit JARVIS", self._quit),
        )

    def _toggle_voice(self):
        """Toggle voice activation."""
        self.state.voice_enabled = not self.state.voice_enabled
        self.state.save()

        if self.on_voice_toggle:
            self.on_voice_toggle(self.state.voice_enabled)

        self.update_status("listening" if self.state.voice_enabled else "idle")
        self.notify(f"Voice {'enabled' if self.state.voice_enabled else 'disabled'}")

    def _run_action(self, action: str):
        """Run a quick action."""
        self.state.last_activity = f"{action} @ {datetime.now().strftime('%H:%M')}"
        self.state.save()

        if self.on_command:
            self.on_command(action)
        else:
            # Default actions
            if action == "sentiment":
                self._run_script("scripts/diagnose_sentiment.py")
            elif action == "wallet":
                self.notify("Checking wallet...")
            elif action == "research":
                if self.on_research:
                    self.on_research("")
            elif action == "status":
                self.notify(f"Daemon: {'Running' if self.state.daemon_running else 'Stopped'}")

    def _run_script(self, script_path: str):
        """Run a Python script in background."""
        import subprocess
        full_path = ROOT / script_path
        if full_path.exists():
            subprocess.Popen(
                [sys.executable, str(full_path)],
                cwd=str(ROOT),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.notify(f"Running {script_path}")

    def _open_link(self, link_type: str):
        """Open external links."""
        links = {
            'telegram': 'https://t.me/kr8tiventry',
            'dashboard': 'http://localhost:8000',
            'github': 'https://github.com/Matt-Aurora-Ventures/Jarvis',
        }
        url = links.get(link_type)
        if url:
            webbrowser.open(url)

    def _quit(self):
        """Quit the system tray."""
        self._running = False
        self.state.save()
        if self.icon:
            self.icon.stop()

    def update_status(self, status: str):
        """Update tray icon status."""
        self._status = status
        if self.icon:
            self.icon.icon = self._create_icon_image(status)
            self.icon.menu = self._build_menu()

    def notify(self, message: str, title: str = "JARVIS"):
        """Show notification popup."""
        self.state.pending_notifications.append(message)
        self.state.save()

        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def set_daemon_status(self, running: bool):
        """Update daemon running status."""
        self.state.daemon_running = running
        self.state.save()
        if self.icon:
            self.icon.menu = self._build_menu()

    def log_activity(self, activity: str):
        """Log an activity for display."""
        self.state.last_activity = activity
        self.state.quick_actions.append(activity)
        self.state.save()

    def start(self):
        """Start the system tray in background thread."""
        if not PYSTRAY_AVAILABLE:
            logger.error("Cannot start tray: pystray not installed")
            return

        def run_tray():
            self._running = True
            self.icon = pystray.Icon(
                "jarvis",
                self._create_icon_image(self._status),
                "JARVIS",
                self._build_menu()
            )
            self.icon.run()

        thread = threading.Thread(target=run_tray, daemon=True)
        thread.start()
        logger.info("System tray started")

    def stop(self):
        """Stop the system tray."""
        self._quit()


class CrossSystemStateSync:
    """
    Synchronize state across JARVIS components.

    Provides:
    - Shared state file (JSON)
    - Event bus for real-time updates
    - Recovery from crashes
    - Cross-process communication
    """

    STATE_FILE = ROOT / "data" / "cross_system_state.json"
    LOCK_FILE = ROOT / "data" / ".state_lock"

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._subscribers: List[Callable[[str, Any], None]] = []
        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    self._state = json.load(f)
            except Exception:
                self._state = {}

        # Ensure required keys
        self._state.setdefault('components', {})
        self._state.setdefault('last_sync', None)
        self._state.setdefault('active_sessions', [])
        self._state.setdefault('pending_actions', [])
        self._state.setdefault('memory_context', {})

    def _save_state(self):
        """Persist state to disk."""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._state['last_sync'] = datetime.now().isoformat()

        with open(self.STATE_FILE, 'w') as f:
            json.dump(self._state, f, indent=2, default=str)

    def register_component(self, name: str, status: str = "running"):
        """Register a running component."""
        self._state['components'][name] = {
            'status': status,
            'started': datetime.now().isoformat(),
            'last_heartbeat': datetime.now().isoformat(),
        }
        self._save_state()
        self._notify(f"component:{name}", status)

    def heartbeat(self, name: str):
        """Update component heartbeat."""
        if name in self._state['components']:
            self._state['components'][name]['last_heartbeat'] = datetime.now().isoformat()
            self._save_state()

    def unregister_component(self, name: str):
        """Remove a component."""
        if name in self._state['components']:
            del self._state['components'][name]
            self._save_state()

    def set_context(self, key: str, value: Any):
        """Set shared context value."""
        self._state['memory_context'][key] = value
        self._save_state()
        self._notify(f"context:{key}", value)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get shared context value."""
        return self._state['memory_context'].get(key, default)

    def queue_action(self, action: Dict[str, Any]):
        """Queue an action for another component."""
        action['queued_at'] = datetime.now().isoformat()
        self._state['pending_actions'].append(action)
        self._save_state()
        self._notify("action:queued", action)

    def get_pending_actions(self, component: str) -> List[Dict]:
        """Get pending actions for a component."""
        actions = [
            a for a in self._state['pending_actions']
            if a.get('target') == component
        ]
        # Remove claimed actions
        self._state['pending_actions'] = [
            a for a in self._state['pending_actions']
            if a.get('target') != component
        ]
        self._save_state()
        return actions

    def subscribe(self, callback: Callable[[str, Any], None]):
        """Subscribe to state changes."""
        self._subscribers.append(callback)

    def _notify(self, event: str, data: Any):
        """Notify subscribers of state change."""
        for callback in self._subscribers:
            try:
                callback(event, data)
            except Exception as e:
                logger.error(f"State sync callback error: {e}")

    def get_all_components(self) -> Dict[str, Dict]:
        """Get all registered components."""
        return self._state.get('components', {})

    def cleanup_stale(self, max_age_seconds: int = 300):
        """Remove components with stale heartbeats."""
        now = datetime.now()
        stale = []

        for name, info in self._state['components'].items():
            try:
                last_hb = datetime.fromisoformat(info['last_heartbeat'])
                if (now - last_hb).total_seconds() > max_age_seconds:
                    stale.append(name)
            except Exception:
                stale.append(name)

        for name in stale:
            del self._state['components'][name]
            logger.info(f"Removed stale component: {name}")

        if stale:
            self._save_state()


# Global instances
_tray: Optional[JarvisSystemTray] = None
_state_sync: Optional[CrossSystemStateSync] = None


def get_tray() -> JarvisSystemTray:
    """Get singleton tray instance."""
    global _tray
    if _tray is None:
        _tray = JarvisSystemTray()
    return _tray


def get_state_sync() -> CrossSystemStateSync:
    """Get singleton state sync instance."""
    global _state_sync
    if _state_sync is None:
        _state_sync = CrossSystemStateSync()
    return _state_sync


def start_tray_daemon():
    """Start tray as daemon (for use with main daemon)."""
    tray = get_tray()
    sync = get_state_sync()

    # Register with state sync
    sync.register_component("system_tray", "running")

    # Wire up state sync to tray
    def on_state_change(event: str, data: Any):
        if event.startswith("component:"):
            tray.set_daemon_status(len(sync.get_all_components()) > 1)

    sync.subscribe(on_state_change)

    # Start tray
    tray.start()

    return tray, sync


if __name__ == "__main__":
    # Test the system tray
    logging.basicConfig(level=logging.INFO)
    tray, sync = start_tray_daemon()

    print("JARVIS System Tray started. Check your system tray!")
    print("Press Ctrl+C to exit...")

    try:
        while True:
            time.sleep(1)
            sync.heartbeat("system_tray")
    except KeyboardInterrupt:
        print("\nShutting down...")
        tray.stop()
