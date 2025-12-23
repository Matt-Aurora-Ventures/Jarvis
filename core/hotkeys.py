import threading
import time
from typing import Callable

from core import config, state


def _normalize_hotkey(combo: str) -> str:
    parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
    mapped = []
    for part in parts:
        if part in ("ctrl", "control"):
            mapped.append("<ctrl>")
        elif part in ("shift",):
            mapped.append("<shift>")
        elif part in ("alt", "option"):
            mapped.append("<alt>")
        elif part in ("cmd", "command", "meta", "super"):
            mapped.append("<cmd>")
        elif part in ("up", "down", "left", "right"):
            mapped.append(f"<{part}>")
        else:
            mapped.append(part)
    return "+".join(mapped)


class HotkeyManager(threading.Thread):
    def __init__(self, on_trigger: Callable[[], None]) -> None:
        super().__init__(daemon=True)
        self._on_trigger = on_trigger
        self._stop_event = threading.Event()
        self._listener = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    def run(self) -> None:
        cfg = config.load_config()
        hotkey_cfg = cfg.get("hotkeys", {})
        if not hotkey_cfg.get("enabled", True):
            state.update_state(hotkeys_enabled=False, hotkey_error="disabled")
            return

        try:
            from pynput import keyboard
        except Exception:
            state.update_state(hotkeys_enabled=False, hotkey_error="pynput_unavailable")
            return

        raw_combo = hotkey_cfg.get("chat_activation", "ctrl+shift+up")
        combo = _normalize_hotkey(raw_combo)

        def _activate() -> None:
            if self._stop_event.is_set():
                return
            try:
                self._on_trigger()
            except Exception:
                state.update_state(hotkey_error="activation_failed")

        try:
            self._listener = keyboard.GlobalHotKeys({combo: _activate})
            self._listener.start()
            state.update_state(
                hotkeys_enabled=True, hotkey_combo=raw_combo, hotkey_error="none"
            )
            while not self._stop_event.is_set():
                time.sleep(0.25)
        except Exception:
            state.update_state(hotkeys_enabled=False, hotkey_error="hotkey_unavailable")
        finally:
            if self._listener:
                try:
                    self._listener.stop()
                except Exception:
                    pass
