import threading
import time
from typing import Callable

from core import config, input_broker, state


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
        self._broker = input_broker.get_input_broker()
        self._subscription_id = None
        self._pressed = set()
        self._required = set()
        self._combo_active = False

    def stop(self) -> None:
        self._stop_event.set()
        if self._subscription_id is not None:
            self._broker.unsubscribe_keyboard(self._subscription_id)
            self._subscription_id = None

    def run(self) -> None:
        cfg = config.load_config()
        hotkey_cfg = cfg.get("hotkeys", {})
        if not hotkey_cfg.get("enabled", True):
            state.update_state(hotkeys_enabled=False, hotkey_error="disabled")
            return

        raw_combo = hotkey_cfg.get("chat_activation", "ctrl+shift+up")
        combo = _normalize_hotkey(raw_combo)
        self._required = {part for part in combo.split("+") if part}

        def _activate() -> None:
            if self._stop_event.is_set():
                return
            try:
                self._on_trigger()
            except Exception as e:
                state.update_state(hotkey_error="activation_failed")

        try:
            def _on_key(event_type, key) -> None:
                name = input_broker.normalize_key(key)
                if not name:
                    return
                if event_type == "press":
                    self._pressed.add(name)
                    if self._required and self._required.issubset(self._pressed):
                        if not self._combo_active:
                            self._combo_active = True
                            _activate()
                elif event_type == "release":
                    if name in self._pressed:
                        self._pressed.remove(name)
                    if self._combo_active and not self._required.issubset(self._pressed):
                        self._combo_active = False

            self._subscription_id = self._broker.subscribe_keyboard(_on_key)
            if not self._broker.ensure_keyboard():
                raise RuntimeError("keyboard_listener_unavailable")
            state.update_state(
                hotkeys_enabled=True, hotkey_combo=raw_combo, hotkey_error="none"
            )
            while not self._stop_event.is_set():
                time.sleep(0.25)
        except Exception as e:
            state.update_state(hotkeys_enabled=False, hotkey_error="hotkey_unavailable")
        finally:
            if self._subscription_id is not None:
                self._broker.unsubscribe_keyboard(self._subscription_id)
                self._subscription_id = None
